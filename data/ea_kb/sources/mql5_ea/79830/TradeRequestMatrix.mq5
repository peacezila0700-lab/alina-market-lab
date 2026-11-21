//+------------------------------------------------------------------+
//|                                           TradeRequestMatrix.mq5 |
//|                                   Copyright 2026, OLUWASOMIDOTUN |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright   "Copyright 2026, OLUWASOMIDOTUN"
#property link        "https://www.mql5.com"
#property version     "1.00"
#property description "Part 4 of the regression-testing series."
#property description "Builds a fixed matrix of valid and invalid trade requests (stops, volume,"
#property description "close and modify) and checks every one with OrderCheck(). Nothing is sent."
#property description "Press R on the chart to run the matrix again."

//--- object name prefix, every chart object of this program starts with it
#define PREFIX            "TRM_"
//--- number of test rows in the matrix
#define ROWS              20
//--- text lines in the panel: 3 header lines, one line per row, 2 summary lines
#define PANEL_LINES       (ROWS + 5)
//--- a position ticket that does not exist on any account
#define UNKNOWN_TICKET    4294967294
//--- virtual key code of the "R" key
#define KEY_R             82

//+------------------------------------------------------------------+
//| Enumerations                                                     |
//+------------------------------------------------------------------+
//--- result of one row
enum ENUM_VERDICT
  {
   V_NA = 0,           // row cannot be built for this symbol or account
   V_PASS = 1,         // the server answered as the rules predict
   V_FAIL = 2,         // the server answered differently from the rules
   V_INCONCLUSIVE = 3  // the server could not judge the request (market closed, no money ...)
  };

//--- what the rules predict for a row
enum ENUM_EXPECT
  {
   X_NONE = 0,         // no expectation (row is not applicable)
   X_ACCEPT = 1,       // the request is valid and must be accepted
   X_REJECT = 2        // the request is invalid and must be rejected with a listed code
  };

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input group "Test scope"
input string InpSymbol            = "";    // Symbol to test (empty = chart symbol)
input double InpVolume            = 0.0;   // Base volume in lots (0 = symbol minimum)
input bool   InpUsePosition       = true;  // Use an open position for the close and modify rows
input long   InpPositionMagic     = -1;    // Only use positions with this magic (-1 = any)

input group "Distances (points)"
input int    InpFallbackStopPoints = 50;   // Distance used when the stops level is 0
input int    InpWrongSidePoints    = 100;  // How far a wrong-side stop is placed

input group "Run control"
input bool   InpRunOnStart        = true;  // Run the matrix when the EA starts
input int    InpAutoRepeatSec     = 0;     // Repeat every N seconds (0 = off, minimum 5)
input bool   InpLogResults        = true;  // Print every row to the Experts journal
input string InpBaselineDigest    = "";    // Digest of a known-good run (empty = no comparison)

input group "Display"
input bool   InpShowPanel         = true;  // Show the result panel
input bool   InpShowLevels        = true;  // Draw the stops-level boundaries on the chart
input color  InpTextColor         = clrSilver; // Panel text color
input color  InpFailColor         = clrWhite;  // Color of FAIL rows
input int    InpFontSize          = 8;     // Panel font size
input int    InpPanelX            = 8;     // Panel X offset in pixels
input int    InpPanelY            = 14;    // Panel Y offset in pixels

//+------------------------------------------------------------------+
//| Snapshot of the symbol and position state used to build requests |
//+------------------------------------------------------------------+
struct Snapshot
  {
   string                  symbol;       // tested symbol
   double                  bid;          // current Bid
   double                  ask;          // current Ask
   double                  point;        // point size
   int                     digits;       // price digits
   long                    stopsLevel;   // SYMBOL_TRADE_STOPS_LEVEL in points
   long                    freezeLevel;  // SYMBOL_TRADE_FREEZE_LEVEL in points
   double                  vmin;         // minimum volume
   double                  vmax;         // maximum volume
   double                  vstep;        // volume step
   double                  volume;       // base volume used by the rows
   long                    distance;     // boundary distance in points used by the stop rows
   ENUM_ORDER_TYPE_FILLING filling;      // filling mode the symbol supports
   bool                    hasPos;       // a usable position exists
   ulong                   ticket;       // position ticket
   ENUM_POSITION_TYPE      ptype;        // position direction
   double                  pvol;         // position volume
   double                  psl;          // position stop loss
   double                  ptp;          // position take profit
   long                    magic;        // magic number of the position
  };

//+------------------------------------------------------------------+
//| Globals                                                          |
//+------------------------------------------------------------------+
string            g_symbol;                 // symbol under test
Snapshot          g_snap;                   // last snapshot
MqlTradeRequest   g_req[ROWS];              // request of every row
string            g_name[ROWS];             // row title
string            g_naReason[ROWS];         // why a row is not applicable
int               g_expKind[ROWS];          // ENUM_EXPECT of every row
int               g_exp1[ROWS];             // first accepted retcode of a reject row
int               g_exp2[ROWS];             // second accepted retcode of a reject row (0 = none)
int               g_got[ROWS];              // retcode returned by OrderCheck()
int               g_verdict[ROWS];          // ENUM_VERDICT of every row
bool              g_pendingRun = false;     // first run is waiting for quotes
int               g_attempts   = 0;         // quote-wait attempts so far
datetime          g_nextRun    = 0;         // next automatic run
string            g_digest     = "";        // digest of the last run
string            g_message    = "";        // status message when no run is possible
int               g_pass = 0, g_fail = 0, g_na = 0, g_inc = 0; // counters of the last run
int               g_repeatSec  = 0;         // validated repeat interval

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
//--- resolve the symbol and make sure it is in Market Watch
   g_symbol = (StringLen(InpSymbol) > 0) ? InpSymbol : _Symbol;
   if(!SymbolSelect(g_symbol, true))
     {
      Print("TradeRequestMatrix: symbol not available: ", g_symbol);
      return(INIT_FAILED);
     }
//--- keep the interval sane, a value between 1 and 4 seconds is raised to 5
   g_repeatSec = (InpAutoRepeatSec <= 0) ? 0 : MathMax(InpAutoRepeatSec, 5);
//--- one-second timer drives the first run and the optional repeat
   if(!EventSetTimer(1))
      return(INIT_FAILED);
   g_pendingRun = InpRunOnStart;
   g_attempts   = 0;
   g_message    = "Waiting for quotes ...";
   ResetResults();
   Redraw();
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   EventKillTimer();
//--- remove the panel and the level lines
   ObjectsDeleteAll(0, PREFIX);
   ChartRedraw(0);
  }

//+------------------------------------------------------------------+
//| Tick function: the matrix does not depend on ticks               |
//+------------------------------------------------------------------+
void OnTick()
  {
  }

//+------------------------------------------------------------------+
//| Timer: first run, then the optional repeat                       |
//+------------------------------------------------------------------+
void OnTimer()
  {
   if(g_pendingRun)
     {
      //--- RunMatrix() returns false while the symbol has no quotes
      if(RunMatrix())
         g_pendingRun = false;
      else
         if(++g_attempts >= 30)
           {
            g_pendingRun = false;
            g_message    = "No quotes for " + g_symbol + ". Press R to try again.";
            Redraw();
           }
      return;
     }
   if(g_repeatSec > 0 && TimeLocal() >= g_nextRun)
      RunMatrix();
  }

//+------------------------------------------------------------------+
//| Chart event: R runs the matrix again                             |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   if(id == CHARTEVENT_KEYDOWN && lparam == KEY_R)
      RunMatrix();
  }

//+------------------------------------------------------------------+
//| Clear the results of the previous run                            |
//+------------------------------------------------------------------+
void ResetResults()
  {
   for(int i = 0; i < ROWS; i++)
     {
      g_name[i]     = "";
      g_naReason[i] = "";
      g_expKind[i]  = X_NONE;
      g_exp1[i]     = 0;
      g_exp2[i]     = 0;
      g_got[i]      = 0;
      g_verdict[i]  = V_NA;
      ZeroMemory(g_req[i]);
     }
   g_pass = 0;
   g_fail = 0;
   g_na   = 0;
   g_inc  = 0;
   g_digest = "";
  }

//+------------------------------------------------------------------+
//| Read symbol and position state. False when there are no quotes   |
//+------------------------------------------------------------------+
bool LoadSnapshot(const string sym, Snapshot &s)
  {
   s.symbol = sym;
   s.bid    = SymbolInfoDouble(sym, SYMBOL_BID);
   s.ask    = SymbolInfoDouble(sym, SYMBOL_ASK);
   s.point  = SymbolInfoDouble(sym, SYMBOL_POINT);
   if(s.bid <= 0.0 || s.ask <= 0.0 || s.point <= 0.0)
      return(false);
   s.digits      = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   s.stopsLevel  = SymbolInfoInteger(sym, SYMBOL_TRADE_STOPS_LEVEL);
   s.freezeLevel = SymbolInfoInteger(sym, SYMBOL_TRADE_FREEZE_LEVEL);
   s.vmin        = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   s.vmax        = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);
   s.vstep       = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);
   if(s.vmin <= 0.0 || s.vmax < s.vmin)
      return(false);

//--- base volume: the input snapped to the step grid and clamped to the limits
   double v = (InpVolume > 0.0) ? InpVolume : s.vmin;
   v = MathMax(s.vmin, MathMin(s.vmax, v));
   if(s.vstep > 0.0)
      v = s.vmin + MathRound((v - s.vmin) / s.vstep) * s.vstep;
   s.volume = NormalizeDouble(MathMin(v, s.vmax), 8);

//--- distance used for the "at the limit" rows
   s.distance = (s.stopsLevel > 0) ? s.stopsLevel : (long)MathMax(InpFallbackStopPoints, 1);

//--- filling mode: pick one the symbol allows, otherwise OrderCheck() answers 10030
   const int flags = (int)SymbolInfoInteger(sym, SYMBOL_FILLING_MODE);
   if((flags & SYMBOL_FILLING_FOK) != 0)
      s.filling = ORDER_FILLING_FOK;
   else
      if((flags & SYMBOL_FILLING_IOC) != 0)
         s.filling = ORDER_FILLING_IOC;
      else
         s.filling = ORDER_FILLING_RETURN;

//--- first matching open position of the symbol (read only, it is never touched)
   s.hasPos = false;
   s.ticket = 0;
   s.ptype  = POSITION_TYPE_BUY;
   s.pvol   = 0.0;
   s.psl    = 0.0;
   s.ptp    = 0.0;
   s.magic  = 0;
   if(InpUsePosition)
     {
      for(int i = 0; i < PositionsTotal(); i++)
        {
         if(PositionGetSymbol(i) != sym)
            continue;
         const long mg = PositionGetInteger(POSITION_MAGIC);
         if(InpPositionMagic >= 0 && mg != InpPositionMagic)
            continue;
         s.hasPos = true;
         s.ticket = (ulong)PositionGetInteger(POSITION_TICKET);
         s.ptype  = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
         s.pvol   = PositionGetDouble(POSITION_VOLUME);
         s.psl    = PositionGetDouble(POSITION_SL);
         s.ptp    = PositionGetDouble(POSITION_TP);
         s.magic  = mg;
         break;
        }
     }
   return(true);
  }

//+------------------------------------------------------------------+
//| Normalize a price to the symbol digits                           |
//+------------------------------------------------------------------+
double Px(const Snapshot &s, const double price)
  {
   return(NormalizeDouble(price, s.digits));
  }

//+------------------------------------------------------------------+
//| Start a market request: fills the fields every row shares        |
//+------------------------------------------------------------------+
void BeginDeal(const int id, const Snapshot &s, const ENUM_ORDER_TYPE type, const double volume)
  {
   ZeroMemory(g_req[id]);
   g_req[id].action       = TRADE_ACTION_DEAL;
   g_req[id].symbol       = s.symbol;
   g_req[id].volume       = volume;
   g_req[id].type         = type;
   g_req[id].price        = (type == ORDER_TYPE_BUY) ? s.ask : s.bid;
   g_req[id].deviation    = 20;
   g_req[id].type_filling = s.filling;
   g_req[id].type_time    = ORDER_TIME_GTC;
   g_req[id].comment      = "TRM";
  }

//+------------------------------------------------------------------+
//| Describe one row: title and what the rules predict               |
//+------------------------------------------------------------------+
void Describe(const int id, const string name, const ENUM_EXPECT kind, const int c1 = 0, const int c2 = 0)
  {
   g_name[id]    = name;
   g_expKind[id] = kind;
   g_exp1[id]    = c1;
   g_exp2[id]    = c2;
  }

//+------------------------------------------------------------------+
//| Mark a row as not applicable                                     |
//+------------------------------------------------------------------+
void MarkNA(const int id, const string name, const string reason)
  {
   g_name[id]     = name;
   g_expKind[id]  = X_NONE;
   g_naReason[id] = reason;
   ZeroMemory(g_req[id]);
  }

//+------------------------------------------------------------------+
//| Build the request of one row from the snapshot                   |
//+------------------------------------------------------------------+
void BuildRow(const int id, const Snapshot &s)
  {
   const double pt   = s.point;
   const double D    = (double)s.distance;                       // boundary distance in points
   const double W    = (double)MathMax(InpWrongSidePoints, 1);   // wrong-side distance in points
   const bool   dyn  = (s.stopsLevel == 0);                      // stops level 0 = dynamic, no fixed limit
   const double vbad = (s.vstep > 0.0) ? s.vstep : s.vmin;       // one step, used to leave the limits
   double       sl = 0.0, tp = 0.0;

   switch(id)
     {
      //--- valid controls: market orders without stops
      case 0:
         Describe(id, "BUY market, no stops", X_ACCEPT);
         BeginDeal(id, s, ORDER_TYPE_BUY, s.volume);
         break;
      case 1:
         Describe(id, "SELL market, no stops", X_ACCEPT);
         BeginDeal(id, s, ORDER_TYPE_SELL, s.volume);
         break;

      //--- stops exactly at the stops level: the boundary itself is valid
      case 2:
         sl = Px(s, s.bid - D * pt);
         if(sl <= 0.0)
           {
            MarkNA(id, "BUY SL at the limit", "price too low");
            break;
           }
         Describe(id, "BUY SL at the limit", X_ACCEPT);
         BeginDeal(id, s, ORDER_TYPE_BUY, s.volume);
         g_req[id].sl = sl;
         break;
      case 3:
         Describe(id, "BUY TP at the limit", X_ACCEPT);
         BeginDeal(id, s, ORDER_TYPE_BUY, s.volume);
         g_req[id].tp = Px(s, s.bid + D * pt);
         break;
      case 4:
         Describe(id, "SELL SL at the limit", X_ACCEPT);
         BeginDeal(id, s, ORDER_TYPE_SELL, s.volume);
         g_req[id].sl = Px(s, s.ask + D * pt);
         break;
      case 5:
         tp = Px(s, s.ask - D * pt);
         if(tp <= 0.0)
           {
            MarkNA(id, "SELL TP at the limit", "price too low");
            break;
           }
         Describe(id, "SELL TP at the limit", X_ACCEPT);
         BeginDeal(id, s, ORDER_TYPE_SELL, s.volume);
         g_req[id].tp = tp;
         break;

      //--- stops one point inside the stops level: must be rejected with INVALID_STOPS
      case 6:
         sl = Px(s, s.bid - (D - 1.0) * pt);
         if(dyn || sl <= 0.0)
           {
            MarkNA(id, "BUY SL 1 pt inside", dyn ? "stops level is 0" : "price too low");
            break;
           }
         Describe(id, "BUY SL 1 pt inside", X_REJECT, 10016);
         BeginDeal(id, s, ORDER_TYPE_BUY, s.volume);
         g_req[id].sl = sl;
         break;
      case 7:
         if(dyn)
           {
            MarkNA(id, "BUY TP 1 pt inside", "stops level is 0");
            break;
           }
         Describe(id, "BUY TP 1 pt inside", X_REJECT, 10016);
         BeginDeal(id, s, ORDER_TYPE_BUY, s.volume);
         g_req[id].tp = Px(s, s.bid + (D - 1.0) * pt);
         break;
      case 8:
         if(dyn)
           {
            MarkNA(id, "SELL SL 1 pt inside", "stops level is 0");
            break;
           }
         Describe(id, "SELL SL 1 pt inside", X_REJECT, 10016);
         BeginDeal(id, s, ORDER_TYPE_SELL, s.volume);
         g_req[id].sl = Px(s, s.ask + (D - 1.0) * pt);
         break;
      case 9:
         tp = Px(s, s.ask - (D - 1.0) * pt);
         if(dyn || tp <= 0.0)
           {
            MarkNA(id, "SELL TP 1 pt inside", dyn ? "stops level is 0" : "price too low");
            break;
           }
         Describe(id, "SELL TP 1 pt inside", X_REJECT, 10016);
         BeginDeal(id, s, ORDER_TYPE_SELL, s.volume);
         g_req[id].tp = tp;
         break;

      //--- stop loss on the profit side of the price: always invalid
      case 10:
         Describe(id, "BUY SL above price", X_REJECT, 10016);
         BeginDeal(id, s, ORDER_TYPE_BUY, s.volume);
         g_req[id].sl = Px(s, s.ask + W * pt);
         break;
      case 11:
         sl = Px(s, s.bid - W * pt);
         if(sl <= 0.0)
           {
            MarkNA(id, "SELL SL below price", "price too low");
            break;
           }
         Describe(id, "SELL SL below price", X_REJECT, 10016);
         BeginDeal(id, s, ORDER_TYPE_SELL, s.volume);
         g_req[id].sl = sl;
         break;

      //--- volume outside the symbol rules: INVALID_VOLUME
      case 12:
         Describe(id, "Volume below minimum", X_REJECT, 10014);
         BeginDeal(id, s, ORDER_TYPE_BUY, NormalizeDouble(s.vmin * 0.5, 8));
         break;
      case 13:
         Describe(id, "Volume above maximum", X_REJECT, 10014);
         BeginDeal(id, s, ORDER_TYPE_BUY, NormalizeDouble(s.vmax + vbad, 8));
         break;
      case 14:
         if(s.vstep <= 0.0)
           {
            MarkNA(id, "Volume off the step grid", "volume step is 0");
            break;
           }
         Describe(id, "Volume off the step grid", X_REJECT, 10014);
         BeginDeal(id, s, ORDER_TYPE_BUY, NormalizeDouble(s.vmin + s.vstep * 0.5, 8));
         break;

      //--- closing: a valid close, a close larger than the position, a ticket that does not exist
      case 15:
         if(!s.hasPos)
           {
            MarkNA(id, "Close, full volume", "no open position");
            break;
           }
         Describe(id, "Close, full volume", X_ACCEPT);
         BeginDeal(id, s, (s.ptype == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY, s.pvol);
         g_req[id].position = s.ticket;
         break;
      case 16:
         if(!s.hasPos)
           {
            MarkNA(id, "Close larger than position", "no open position");
            break;
           }
         Describe(id, "Close larger than position", X_REJECT, 10038, 10014);
         BeginDeal(id, s, (s.ptype == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY,
                   NormalizeDouble(s.pvol + vbad, 8));
         g_req[id].position = s.ticket;
         break;
      case 17:
         Describe(id, "Close unknown ticket", X_REJECT, 10036, 10013);
         BeginDeal(id, s, ORDER_TYPE_SELL, s.volume);
         g_req[id].position = UNKNOWN_TICKET;
         break;

      //--- modifying: unchanged levels and a stop on the wrong side
      case 18:
         if(!s.hasPos)
           {
            MarkNA(id, "Modify, nothing changed", "no open position");
            break;
           }
         Describe(id, "Modify, nothing changed", X_REJECT, 10025);
         ZeroMemory(g_req[id]);
         g_req[id].action   = TRADE_ACTION_SLTP;
         g_req[id].symbol   = s.symbol;
         g_req[id].position = s.ticket;
         g_req[id].sl       = s.psl;
         g_req[id].tp       = s.ptp;
         g_req[id].magic    = s.magic;
         break;
      case 19:
         if(!s.hasPos)
           {
            MarkNA(id, "Modify, SL on wrong side", "no open position");
            break;
           }
         sl = (s.ptype == POSITION_TYPE_BUY) ? Px(s, s.ask + W * pt) : Px(s, s.bid - W * pt);
         if(sl <= 0.0)
           {
            MarkNA(id, "Modify, SL on wrong side", "price too low");
            break;
           }
         Describe(id, "Modify, SL on wrong side", X_REJECT, 10016);
         ZeroMemory(g_req[id]);
         g_req[id].action   = TRADE_ACTION_SLTP;
         g_req[id].symbol   = s.symbol;
         g_req[id].position = s.ticket;
         g_req[id].sl       = sl;
         g_req[id].tp       = s.ptp;
         g_req[id].magic    = s.magic;
         break;
     }
  }

//+------------------------------------------------------------------+
//| Codes that mean "the server could not judge this request"        |
//+------------------------------------------------------------------+
bool IsTransient(const int rc)
  {
   switch(rc)
     {
      case 10017: // trade disabled
      case 10018: // market closed
      case 10019: // not enough money
      case 10021: // no quotes
      case 10024: // too many requests
      case 10026: // algo trading disabled by the server
      case 10027: // algo trading disabled by the terminal
      case 10029: // order or position frozen
      case 10031: // no connection
         return(true);
     }
   return(false);
  }

//+------------------------------------------------------------------+
//| Judge one row: compare the server answer with the prediction     |
//+------------------------------------------------------------------+
ENUM_VERDICT Judge(const int id, const bool callOk, const int rc)
  {
   if(g_expKind[id] == X_NONE)
      return(V_NA);
//--- the call itself failed and gave no server retcode: nothing to compare
   if(rc < 0 || (!callOk && rc == 0))
      return(V_INCONCLUSIVE);
   const bool accepted = (rc == 0 || rc == 10009);
   if(g_expKind[id] == X_ACCEPT)
     {
      if(accepted)
         return(V_PASS);
      return(IsTransient(rc) ? V_INCONCLUSIVE : V_FAIL);
     }
//--- X_REJECT: the code must be one of the listed ones
   if(!accepted && (rc == g_exp1[id] || (g_exp2[id] != 0 && rc == g_exp2[id])))
      return(V_PASS);
   return((!accepted && IsTransient(rc)) ? V_INCONCLUSIVE : V_FAIL);
  }

//+------------------------------------------------------------------+
//| FNV-1a step over the four bytes of a value                       |
//+------------------------------------------------------------------+
uint FnvAdd(uint h, const long value)
  {
   uint u = (uint)value;
   for(int b = 0; b < 4; b++)
     {
      h ^= (u & 0xFF);
      h *= 16777619;
      u >>= 8;
     }
   return(h);
  }

//+------------------------------------------------------------------+
//| Run the whole matrix once. False when the symbol has no quotes   |
//+------------------------------------------------------------------+
bool RunMatrix()
  {
   if(!LoadSnapshot(g_symbol, g_snap))
     {
      g_message = "No quotes for " + g_symbol + " yet ...";
      Redraw();
      return(false);
     }
   ResetResults();
   g_message = "";

//--- build, check and judge every row; OrderCheck() never sends anything
   uint h = (uint)2166136261;
   for(int i = 0; i < ROWS; i++)
     {
      BuildRow(i, g_snap);
      int  rc = 0;
      bool ok = false;
      if(g_expKind[i] != X_NONE)
        {
         MqlTradeCheckResult chk;
         ZeroMemory(chk);
         ok = OrderCheck(g_req[i], chk);
         rc = (int)chk.retcode;
         //--- a failed call without a retcode is reported as a negative error code
         if(!ok && rc == 0)
            rc = -GetLastError();
        }
      g_got[i]     = rc;
      g_verdict[i] = (int)Judge(i, ok, rc);
      switch(g_verdict[i])
        {
         case V_PASS:
            g_pass++;
            break;
         case V_FAIL:
            g_fail++;
            break;
         case V_INCONCLUSIVE:
            g_inc++;
            break;
         default:
            g_na++;
        }
      h = FnvAdd(h, i);
      h = FnvAdd(h, g_verdict[i]);
      h = FnvAdd(h, rc);
      if(InpLogResults)
         PrintFormat("TRM %02d %-26s expect=%-6s got=%-6d %s %s", i + 1, g_name[i], ExpectText(i), rc,
                     VerdictText(g_verdict[i]), g_naReason[i]);
     }
   g_digest = StringFormat("%08X", h);
   if(InpLogResults)
      PrintFormat("TRM %s: pass=%d fail=%d n/a=%d inconclusive=%d digest=%s", g_symbol, g_pass, g_fail, g_na,
                  g_inc, g_digest);

   g_nextRun = TimeLocal() + g_repeatSec;
   Redraw();
   return(true);
  }

//+------------------------------------------------------------------+
//| Text helpers                                                     |
//+------------------------------------------------------------------+
string VerdictText(const int v)
  {
   switch(v)
     {
      case V_PASS:
         return("PASS");
      case V_FAIL:
         return("FAIL");
      case V_INCONCLUSIVE:
         return("INCONCL");
     }
   return("n/a");
  }

//--- what the rules predict, as shown in the panel
string ExpectText(const int id)
  {
   if(g_expKind[id] == X_NONE)
      return("-");
   if(g_expKind[id] == X_ACCEPT)
      return("accept");
   if(g_exp2[id] != 0)
      return(IntegerToString(g_exp1[id]) + "|" + IntegerToString(g_exp2[id]));
   return(IntegerToString(g_exp1[id]));
  }

//--- overall verdict of the last run
string OverallText()
  {
   if(g_fail > 0)
      return("FAIL");
   if(g_inc > 0)
      return("INCONCLUSIVE");
   return("PASS");
  }

//--- comparison of the digest with the baseline input
string BaselineText()
  {
   if(StringLen(InpBaselineDigest) == 0)
      return("no baseline");
   return((StringCompare(InpBaselineDigest, g_digest, false) == 0) ? "MATCH" : "CHANGED");
  }

//+------------------------------------------------------------------+
//| Create or update one panel line                                  |
//+------------------------------------------------------------------+
void PanelLine(const int index, const string text, const color clr)
  {
   const string name = PREFIX + "L" + IntegerToString(index);
   if(ObjectFind(0, name) < 0)
     {
      ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, name, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_ANCHOR, ANCHOR_LEFT_UPPER);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
     }
   ObjectSetInteger(0, name, OBJPROP_FONTSIZE, InpFontSize);
   ObjectSetInteger(0, name, OBJPROP_XDISTANCE, InpPanelX);
   ObjectSetInteger(0, name, OBJPROP_YDISTANCE, InpPanelY + index * (InpFontSize + 5));
   ObjectSetInteger(0, name, OBJPROP_COLOR, clr);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
  }

//+------------------------------------------------------------------+
//| Create or move one horizontal level line                         |
//+------------------------------------------------------------------+
void LevelLine(const string tag, const double price, const ENUM_LINE_STYLE style, const string text)
  {
   const string name = PREFIX + tag;
   if(ObjectFind(0, name) < 0)
     {
      ObjectCreate(0, name, OBJ_HLINE, 0, 0, price);
      ObjectSetInteger(0, name, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, name, OBJPROP_HIDDEN, true);
      ObjectSetInteger(0, name, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, name, OBJPROP_BACK, true);
     }
   ObjectSetDouble(0, name, OBJPROP_PRICE, price);
   ObjectSetInteger(0, name, OBJPROP_STYLE, style);
   ObjectSetInteger(0, name, OBJPROP_COLOR, clrWhite);
   ObjectSetString(0, name, OBJPROP_TEXT, text);
  }

//+------------------------------------------------------------------+
//| Redraw the panel and the level lines                             |
//+------------------------------------------------------------------+
void Redraw()
  {
   if(InpShowPanel)
     {
      int line = 0;
      PanelLine(line++, "Trade-Request Matrix | " + g_symbol + " | OrderCheck only, nothing is sent", InpTextColor);
      if(StringLen(g_message) > 0)
        {
         PanelLine(line++, g_message, InpTextColor);
         for(; line < PANEL_LINES; line++)
            PanelLine(line, "", InpTextColor);
        }
      else
        {
         PanelLine(line++, StringFormat("bid %s  ask %s  stops %d  freeze %d  vol %s [%s..%s/%s]",
                                        DoubleToString(g_snap.bid, g_snap.digits),
                                        DoubleToString(g_snap.ask, g_snap.digits),
                                        (int)g_snap.stopsLevel, (int)g_snap.freezeLevel,
                                        DoubleToString(g_snap.volume, 2), DoubleToString(g_snap.vmin, 2),
                                        DoubleToString(g_snap.vmax, 2), DoubleToString(g_snap.vstep, 2)),
                   InpTextColor);
         PanelLine(line++, " #  row                        expect      got     verdict", InpTextColor);
         for(int i = 0; i < ROWS; i++)
           {
            const string gotText = (g_expKind[i] == X_NONE) ? "-" : IntegerToString(g_got[i]);
            PanelLine(line++, StringFormat("%2d  %-26s %-11s %-7s %s", i + 1, g_name[i], ExpectText(i), gotText,
                                           VerdictText(g_verdict[i])),
                      (g_verdict[i] == V_FAIL) ? InpFailColor : InpTextColor);
           }
         PanelLine(line++, StringFormat("pass %d  fail %d  n/a %d  inconclusive %d  =>  %s", g_pass, g_fail,
                                        g_na, g_inc, OverallText()),
                   (g_fail > 0) ? InpFailColor : InpTextColor);
         PanelLine(line++, "digest " + g_digest + "  baseline: " + BaselineText() + "  [R] run again", InpTextColor);
        }
     }
   else
      ObjectsDeleteAll(0, PREFIX + "L");

//--- boundaries of the stops level around the current prices
   if(InpShowLevels && StringLen(g_message) == 0 && g_snap.point > 0.0)
     {
      const double d = (double)g_snap.distance * g_snap.point;
      LevelLine("BUY_SL", Px(g_snap, g_snap.bid - d), STYLE_DASH, "BUY SL limit (Bid - level)");
      LevelLine("BUY_TP", Px(g_snap, g_snap.bid + d), STYLE_DOT, "BUY TP limit (Bid + level)");
      LevelLine("SELL_SL", Px(g_snap, g_snap.ask + d), STYLE_DASH, "SELL SL limit (Ask + level)");
      LevelLine("SELL_TP", Px(g_snap, g_snap.ask - d), STYLE_DOT, "SELL TP limit (Ask - level)");
     }
   else
      if(!InpShowLevels)
        {
         ObjectDelete(0, PREFIX + "BUY_SL");
         ObjectDelete(0, PREFIX + "BUY_TP");
         ObjectDelete(0, PREFIX + "SELL_SL");
         ObjectDelete(0, PREFIX + "SELL_TP");
        }
   ChartRedraw(0);
  }
//+------------------------------------------------------------------+
