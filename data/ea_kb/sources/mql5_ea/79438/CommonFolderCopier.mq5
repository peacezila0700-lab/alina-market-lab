//+------------------------------------------------------------------+
//|                                             CommonFolderCopier.mq5 |
//|  Copies positions between MT5 terminals on the same computer     |
//|  (or VPS) through a file in the Common\Files folder.             |
//|  MASTER: attach to one chart of the source account; it writes a  |
//|          snapshot of the open positions several times a second.  |
//|  SLAVE:  attach to one chart of each receiving account; it opens |
//|          the missing positions, syncs SL/TP and volume, and      |
//|          closes the copies when the master position is closed.  |
//|  Use the same "Channel" in master and slaves. Hedging accounts.  |
//+------------------------------------------------------------------+
#property copyright "Augusto Martin D'anna"
#property version   "1.00"
#property description "Local MT5-to-MT5 trade copier through the Common files folder: one EA, Master or Slave mode."
#property description "Lot multiplier or fixed lot, symbol prefix/suffix mapping, optional reverse, SL/TP and partial close sync."

#include <Trade/Trade.mqh>

enum ENUM_COPIER_MODE
  {
   MODE_MASTER = 0, // Master (source account)
   MODE_SLAVE  = 1  // Slave (receiving account)
  };

enum ENUM_LOT_MODE
  {
   LOT_MULTIPLIER = 0, // Master lot x multiplier
   LOT_FIXED      = 1  // Fixed lot
  };

input ENUM_COPIER_MODE InpMode        = MODE_MASTER;    // Mode
input string           InpChannel     = "main";         // Channel name (same in master and slaves)
input int              InpIntervalMs  = 250;            // Update interval, ms
input long             InpMasterMagic = -1;             // Master: copy only this magic (-1 = all)
input ENUM_LOT_MODE    InpLotMode     = LOT_MULTIPLIER; // Slave: lot mode
input double           InpLotValue    = 1.0;            // Slave: multiplier or fixed lot
input string           InpPrefix      = "";             // Slave: symbol prefix on this broker
input string           InpSuffix      = "";             // Slave: symbol suffix on this broker
input bool             InpReverse     = false;          // Slave: copy in the opposite direction
input bool             InpCopySLTP    = true;           // Slave: copy SL and TP
input long             InpSlaveMagic  = 777001;         // Slave: magic number of the copies
input int              InpMaxDelaySec = 10;             // Slave: ignore the master file if older than this

struct SMasterPos
  {
   ulong             ticket;
   string            symbol;
   int               side;      // +1 buy, -1 sell
   double            volume;
   double            sl;
   double            tp;
  };

CTrade g_trade;

string FileName() { return "CFC_" + InpChannel + ".csv"; }

//+------------------------------------------------------------------+
//| MASTER: write the snapshot to a temp file, then replace the real |
//| one, so a slave never reads a half-written file                  |
//+------------------------------------------------------------------+
int WriteSnapshot()
  {
   int shared = 0;
   string tmp = FileName() + ".tmp";
   int h = FileOpen(tmp, FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_COMMON, ',');
   if(h == INVALID_HANDLE)
     {
      PrintFormat("CFC: cannot write %s, error %d", tmp, GetLastError());
      return -1;
     }
   FileWrite(h, "time", (string)(long)TimeGMT());
   for(int i = 0; i < PositionsTotal(); i++)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0 || (InpMasterMagic >= 0 && PositionGetInteger(POSITION_MAGIC) != InpMasterMagic))
         continue;
      FileWrite(h, (string)t, PositionGetString(POSITION_SYMBOL),
                PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY ? "1" : "-1",
                DoubleToString(PositionGetDouble(POSITION_VOLUME), 2),
                DoubleToString(PositionGetDouble(POSITION_SL), 8), DoubleToString(PositionGetDouble(POSITION_TP), 8));
      shared++;
     }
   FileClose(h);
   if(!FileMove(tmp, FILE_COMMON, FileName(), FILE_COMMON | FILE_REWRITE))
      PrintFormat("CFC: cannot replace %s, error %d", FileName(), GetLastError());
   return shared;
  }

//+------------------------------------------------------------------+
//| SLAVE: read the master snapshot; false if missing or too old     |
//+------------------------------------------------------------------+
bool ReadSnapshot(SMasterPos &out[])
  {
   ArrayResize(out, 0);
   int h = FileOpen(FileName(), FILE_READ | FILE_CSV | FILE_ANSI | FILE_COMMON | FILE_SHARE_READ, ',');
   if(h == INVALID_HANDLE)
      return false;
   bool fresh = false;
   if(!FileIsEnding(h) && FileReadString(h) == "time")
      fresh = (long)TimeGMT() - StringToInteger(FileReadString(h)) <= InpMaxDelaySec;
   while(fresh && !FileIsEnding(h))
     {
      SMasterPos p;
      p.ticket = (ulong)StringToInteger(FileReadString(h));
      p.symbol = FileReadString(h);
      p.side = (int)StringToInteger(FileReadString(h));
      p.volume = StringToDouble(FileReadString(h));
      p.sl = StringToDouble(FileReadString(h));
      p.tp = StringToDouble(FileReadString(h));
      if(p.ticket == 0)
         continue;
      int n = ArraySize(out);
      ArrayResize(out, n + 1);
      out[n] = p;
     }
   FileClose(h);
   return fresh;
  }

string Tag(const ulong masterTicket) { return "CFC#" + (string)masterTicket; }

//--- link slave position -> master ticket in a terminal global variable: the comment of a
//--- position can change (e.g. after a partial close), the global variable does not
string LinkName(const ulong slaveTicket) { return "CFC_" + InpChannel + "_" + (string)slaveTicket; }

ulong MasterOf(const ulong slaveTicket)
  {
   if(GlobalVariableCheck(LinkName(slaveTicket)))
      return (ulong)GlobalVariableGet(LinkName(slaveTicket));
   string c = PositionGetString(POSITION_COMMENT);      // fallback: copy opened before a restart
   if(StringFind(c, "CFC#") == 0)
     {
      ulong mt = (ulong)StringToInteger(StringSubstr(c, 4));
      GlobalVariableSet(LinkName(slaveTicket), (double)mt);
      return mt;
     }
   return 0;
  }

double SlaveLot(const string symbol, const double masterLot)
  {
   double lot = InpLotMode == LOT_FIXED ? InpLotValue : masterLot * InpLotValue;
   double step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
   double vmin = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN), vmax = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
   if(step > 0)
      lot = MathFloor(lot / step + 1e-9) * step;
   return MathMin(MathMax(lot, vmin), vmax);
  }

//--- a copied SL/TP only makes sense when the copy has the same direction as the master
void LevelsFor(const SMasterPos &p, double &sl, double &tp)
  {
   sl = 0;
   tp = 0;
   if(InpCopySLTP && !InpReverse)
     {
      sl = p.sl;
      tp = p.tp;
     }
  }

//+------------------------------------------------------------------+
//| SLAVE: make this account mirror the master snapshot              |
//+------------------------------------------------------------------+
void SyncSlave()
  {
   SMasterPos master[];
   if(!ReadSnapshot(master))
     {
      Comment("CommonFolderCopier SLAVE: waiting for a fresh master file (", FileName(), ")");
      return;
     }
   int n = ArraySize(master);
   //--- 1) close copies whose master position is gone; sync volume and SL/TP of the rest
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0 || PositionGetInteger(POSITION_MAGIC) != InpSlaveMagic)
         continue;
      ulong mt = MasterOf(t);
      int k = -1;
      for(int j = 0; j < n; j++)
         if(master[j].ticket == mt)
           {
            k = j;
            break;
           }
      if(k < 0)
        {
         if(g_trade.PositionClose(t))
            GlobalVariableDel(LinkName(t));
         else
            PrintFormat("CFC: close %I64u failed, retcode %u", t, g_trade.ResultRetcode());
         continue;
        }
      string symbol = PositionGetString(POSITION_SYMBOL);
      double want = SlaveLot(symbol, master[k].volume), have = PositionGetDouble(POSITION_VOLUME);
      if(have - want >= SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP) - 1e-9 && !g_trade.PositionClosePartial(t, have - want))
         PrintFormat("CFC: partial close %I64u failed, retcode %u", t, g_trade.ResultRetcode());
      double sl, tp;
      LevelsFor(master[k], sl, tp);
      if(InpCopySLTP && !InpReverse
         && (MathAbs(PositionGetDouble(POSITION_SL) - sl) > SymbolInfoDouble(symbol, SYMBOL_POINT) / 2
             || MathAbs(PositionGetDouble(POSITION_TP) - tp) > SymbolInfoDouble(symbol, SYMBOL_POINT) / 2))
         g_trade.PositionModify(t, sl, tp);
     }
   //--- 2) open the master positions that have no copy yet
   for(int j = 0; j < n; j++)
     {
      bool found = false;
      for(int i = 0; i < PositionsTotal() && !found; i++)
        {
         ulong t = PositionGetTicket(i);
         found = t > 0 && PositionGetInteger(POSITION_MAGIC) == InpSlaveMagic && MasterOf(t) == master[j].ticket;
        }
      if(found)
         continue;
      string symbol = InpPrefix + master[j].symbol + InpSuffix;
      if(!SymbolSelect(symbol, true))
        {
         PrintFormat("CFC: symbol %s not available on this account", symbol);
         continue;
        }
      double sl, tp;
      LevelsFor(master[j], sl, tp);
      int side = InpReverse ? -master[j].side : master[j].side;
      double lot = SlaveLot(symbol, master[j].volume);
      bool ok = side > 0 ? g_trade.Buy(lot, symbol, 0, sl, tp, Tag(master[j].ticket))
                         : g_trade.Sell(lot, symbol, 0, sl, tp, Tag(master[j].ticket));
      if(ok && g_trade.ResultOrder() > 0)               // on hedging accounts the position ticket = opening order ticket
         GlobalVariableSet(LinkName(g_trade.ResultOrder()), (double)master[j].ticket);
      else if(!ok)
         PrintFormat("CFC: copy of %I64u failed, retcode %u", master[j].ticket, g_trade.ResultRetcode());
     }
   Comment(StringFormat("CommonFolderCopier SLAVE  channel %s\nMaster positions: %d", InpChannel, n));
  }

int OnInit()
  {
   if(InpIntervalMs < 50 || InpLotValue <= 0 || InpChannel == "")
     {
      Print("CFC: invalid inputs");
      return INIT_PARAMETERS_INCORRECT;
     }
   if(InpMode == MODE_SLAVE && AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
      Print("CFC: warning - the slave account is not hedging; opposite positions on one symbol will net out");
   g_trade.SetExpertMagicNumber(InpSlaveMagic);
   g_trade.SetDeviationInPoints(50);
   // in the Strategy Tester a ms timer writing a file every event makes the test run for hours: one event per minute there
   EventSetMillisecondTimer(MQLInfoInteger(MQL_TESTER) ? 60000 : InpIntervalMs);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   Comment("");
  }

void OnTimer()
  {
   if(InpMode == MODE_MASTER)
     {
      int shared = WriteSnapshot();
      Comment("CommonFolderCopier MASTER  channel ", InpChannel, "\nPositions shared: ", shared);
     }
   else
      SyncSlave();
  }
//+------------------------------------------------------------------+
