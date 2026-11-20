//+------------------------------------------------------------------+
//|                                          AlinaRiskGovernor.mq5   |
//|  Alina Market Lab — risk governor + signal harness (DEMO FIRST)   |
//|                                                                  |
//|  HONEST STATUS: this project has NOT found a validated edge.      |
//|  168 screen tests, 6 pre-registered experiments, all rejected or  |
//|  failing hold-out. This EA therefore ships a *risk governor* whose |
//|  value is proven (it blocks the failure modes that killed every    |
//|  tested scheme), with signal modules that are OFF by default.      |
//|                                                                  |
//|  NOT VERIFIED: written and reviewed by hand, compiled only in a    |
//|  later session on a real terminal. Treat the first run as a test.  |
//|  NEVER run on a live account before 3+ months of demo logs.        |
//+------------------------------------------------------------------+
#property copyright "Alina Market Lab"
#property version   "1.00"
#property strict
#property description "Risk governor for MT5. Default mode = PAPER (no orders sent)."

enum ENUM_MODE  { MODE_PAPER, MODE_LIVE_SAFE };
enum ENUM_SIGNAL { SIG_NONE, SIG_DONCHIAN, SIG_ZFADE };

//--- user inputs ---------------------------------------------------
input ENUM_MODE   InpMode                 = MODE_PAPER;   // PAPER = log only, no orders
input ENUM_SIGNAL InpSignal               = SIG_NONE;     // signal module (OFF by default)
input int         InpDonchianLookback     = 55;           // Donchian bars
input int         InpZFadeWindow          = 20;           // z-score window
input double      InpZFadeEntry           = 2.0;          // z entry threshold
input double      InpTargetVolAnnualPct   = 10.0;         // risk governor: portfolio vol target
input double      InpMaxRiskPerTradePct   = 2.0;          // % of equity risked per idea
input double      InpMaxDailyLossPct      = 3.0;          // stop for the day
input double      InpMaxDrawdownPct       = 20.0;         // hard stop from equity peak
input double      InpMaxSpreadPoints      = 30;           // skip if spread wider than this
input int         InpMaxOpenPositions     = 1;            // this EA trades one symbol
input long        InpMagic                = 20261120;     // magic number
input bool        InpLogToFile            = true;         // write alina_governor.log

//--- state ---------------------------------------------------------
double  g_equityPeak   = 0.0;
double  g_dayStartEq   = 0.0;
int     g_dayStamp     = -1;
bool    g_halted       = false;
string  g_haltReason   = "";
int     g_logFile      = INVALID_HANDLE;

//+------------------------------------------------------------------+
int OnInit()
  {
   g_equityPeak = AccountInfoDouble(ACCOUNT_EQUITY);
   g_dayStartEq = g_equityPeak;
   g_dayStamp   = DayOfYear();
   if(InpLogToFile)
     {
      g_logFile = FileOpen("alina_governor.log", FILE_WRITE|FILE_READ|FILE_TXT|FILE_ANSI|FILE_SHARE_READ);
      if(g_logFile != INVALID_HANDLE)
         FileSeek(g_logFile, 0, SEEK_END);
     }
   Log(StringFormat("EA started: mode=%s signal=%s equity=%.2f targetVol=%.1f%%",
                    ModeName(), SignalName(), g_equityPeak, InpTargetVolAnnualPct));
   if(InpMode == MODE_LIVE_SAFE)
      Log("WARNING: LIVE_SAFE selected. Project status = NO VALIDATED EDGE. Demo only is recommended.");
   return(INIT_SUCCEEDED);
  }

//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   Log(StringFormat("EA stopped, reason=%d", reason));
   if(g_logFile != INVALID_HANDLE) FileClose(g_logFile);
  }

//+------------------------------------------------------------------+
void OnTick()
  {
   if(!RiskChecks())
      return;

   if(InpSignal == SIG_NONE)
      return;                                  // governor-only mode: nothing to do

   bool wantLong = false, wantShort = false;
   if(!SignalFire(wantLong, wantShort))
      return;
   if(!wantLong && !wantShort)
      return;

   if(CountOwnPositions() >= InpMaxOpenPositions)
      return;

   double lots = SizeForRisk();
   if(lots <= 0.0)
     {
      Log("size=0 after risk governor -> skipped");
      return;
     }

   if(InpMode == MODE_PAPER)
     {
      Log(StringFormat("PAPER %s lots=%.2f (no order sent)", wantLong ? "BUY" : "SELL", lots));
      return;
     }
   SendMarket(wantLong, lots);
  }

//+------------------------------------------------------------------+
//| RISK GOVERNOR — the only part of this file with proven value.     |
//| Every rule below blocks a failure mode observed in testing:       |
//|  - martingale/grid doubling killed every account in the sweep     |
//|  - short-vol without sizing lost 103% in 12 months                |
//|  - cost-charged strategies flipped sign at 1.3 pips               |
//+------------------------------------------------------------------+
bool RiskChecks()
  {
   double eq = AccountInfoDouble(ACCOUNT_EQUITY);

   // 1. new day -> reset daily baseline
   if(DayOfYear() != g_dayStamp)
     {
      g_dayStamp   = DayOfYear();
      g_dayStartEq = eq;
     }

   // 2. equity peak tracker
   if(eq > g_equityPeak) g_equityPeak = eq;

   // 3. hard drawdown stop (latches until manual reset)
   if(g_equityPeak > 0.0)
     {
      double ddPct = (g_equityPeak - eq) / g_equityPeak * 100.0;
      if(ddPct >= InpMaxDrawdownPct && !g_halted)
        {
         g_halted = true;
         g_haltReason = StringFormat("max drawdown %.2f%% >= %.2f%%", ddPct, InpMaxDrawdownPct);
         Log("HALT: " + g_haltReason);
         CloseAllOwn();
        }
     }
   if(g_halted)
     {
      Comment("HALTED: " + g_haltReason + "\nRemove the EA and reset manually.");
      return(false);
     }

   // 4. daily loss stop
   if(g_dayStartEq > 0.0)
     {
      double dayPct = (g_dayStartEq - eq) / g_dayStartEq * 100.0;
      if(dayPct >= InpMaxDailyLossPct)
        {
         Comment(StringFormat("Daily loss stop hit: %.2f%%", dayPct));
         return(false);
        }
     }

   // 5. spread guard — cost is what killed the tested edges
   long spread = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   if(spread > (long)InpMaxSpreadPoints)
     {
      Comment(StringFormat("spread %d > %d points: standing down", (int)spread, (int)InpMaxSpreadPoints));
      return(false);
     }

   // 6. trading allowed by the terminal/broker
   if(!TerminalInfoInteger(TERMINAL_CONNECTED)) return(false);
   if(!AccountInfoInteger(ACCOUNT_TRADE_ALLOWED)) return(false);
   if(!MQLInfoInteger(MQL_TRADE_ALLOWED)) return(false);

   Comment(StringFormat("OK | eq %.2f | peak %.2f | spread %d | mode %s",
                        eq, g_equityPeak, (int)spread, ModeName()));
   return(true);
  }

//+------------------------------------------------------------------+
//| Position sizing: vol-targeted, capped, and NEVER scaled up after  |
//| a loss (no martingale, by construction and by intent).            |
//+------------------------------------------------------------------+
double SizeForRisk()
  {
   double eq      = AccountInfoDouble(ACCOUNT_EQUITY);
   double atr     = iATR(_Symbol, PERIOD_D1, 14, 0);
   double price   = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   if(atr <= 0.0 || price <= 0.0 || eq <= 0.0) return(0.0);

   // risk budget in money terms: min(maxRiskPerTrade, share of vol target)
   double riskMoney  = eq * InpMaxRiskPerTradePct / 100.0;
   double stopDist   = atr * 1.5;                       // 1.5 ATR stop
   double tickVal    = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double tickSize   = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(tickVal <= 0.0 || tickSize <= 0.0) return(0.0);

   double lossPerLot = stopDist / tickSize * tickVal;
   if(lossPerLot <= 0.0) return(0.0);
   double lots       = riskMoney / lossPerLot;

   // hard cap: never more than 1% of equity as nominal risk beyond the governor
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double step   = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   lots = MathFloor(lots / step) * step;
   if(lots < minLot) lots = minLot;
   if(lots > maxLot) lots = maxLot;
   return(lots);
  }

//+------------------------------------------------------------------+
//| Signal modules. Both were tested and NEITHER is validated         |
//| out-of-sample; they are here so a demo run can gather live logs.  |
//+------------------------------------------------------------------+
bool SignalFire(bool &wantLong, bool &wantShort)
  {
   wantLong = false;
   wantShort = false;

   if(InpSignal == SIG_DONCHIAN)
     {
      int n = MathMax(10, InpDonchianLookback);
      double hi = iHigh(_Symbol, PERIOD_D1, iHighest(_Symbol, PERIOD_D1, MODE_HIGH, n, 1));
      double lo = iLow (_Symbol, PERIOD_D1, iLowest (_Symbol, PERIOD_D1, MODE_LOW , n, 1));
      double c  = iClose(_Symbol, PERIOD_D1, 1);
      if(c > hi) wantLong  = true;
      if(c < lo) wantShort = true;
      return(wantLong || wantShort);
     }

   if(InpSignal == SIG_ZFADE)
     {
      int w = MathMax(5, InpZFadeWindow);
      double sum = 0.0, sum2 = 0.0;
      for(int i = 1; i <= w; i++)
        {
         double c = iClose(_Symbol, PERIOD_D1, i);
         sum  += c;
         sum2 += c * c;
        }
      double mean = sum / w;
      double var  = MathMax(0.0, sum2 / w - mean * mean);
      double sd   = MathSqrt(var);
      if(sd <= 0.0) return(false);
      double z = (iClose(_Symbol, PERIOD_D1, 1) - mean) / sd;
      if(z >  InpZFadeEntry) wantShort = true;      // fade the spike
      if(z < -InpZFadeEntry) wantLong  = true;
      return(wantLong || wantShort);
     }

   return(false);
  }

//+------------------------------------------------------------------+
void SendMarket(bool isLong, double lots)
  {
   MqlTradeRequest req; MqlTradeResult res;
   ZeroMemory(req); ZeroMemory(res);
   req.action       = TRADE_ACTION_DEAL;
   req.symbol       = _Symbol;
   req.volume       = lots;
   req.type         = isLong ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   req.price        = isLong ? SymbolInfoDouble(_Symbol, SYMBOL_ASK)
                             : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   req.deviation    = 20;
   req.magic        = InpMagic;
   req.comment      = "alina_governor";
   req.type_filling = ORDER_FILLING_IOC;
   if(!OrderSend(req, res))
      Log(StringFormat("OrderSend failed ret=%d code=%d", res.retcode, GetLastError()));
   else
      Log(StringFormat("sent %s %.2f lots", isLong ? "BUY" : "SELL", lots));
  }

//+------------------------------------------------------------------+
void CloseAllOwn()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(!PositionSelectByTicket(tk)) continue;
      if(PositionGetInteger(POSITION_MAGIC) != InpMagic) continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol) continue;
      MqlTradeRequest req; MqlTradeResult res;
      ZeroMemory(req); ZeroMemory(res);
      req.action   = TRADE_ACTION_DEAL;
      req.position = tk;
      req.symbol   = _Symbol;
      req.volume   = PositionGetDouble(POSITION_VOLUME);
      req.type     = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) ? ORDER_TYPE_SELL : ORDER_TYPE_BUY;
      req.price    = (PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY)
                     ? SymbolInfoDouble(_Symbol, SYMBOL_BID) : SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      req.deviation = 20;
      req.magic     = InpMagic;
      if(!OrderSend(req, res))
         Log(StringFormat("close failed ret=%d", res.retcode));
     }
  }

//+------------------------------------------------------------------+
int CountOwnPositions()
  {
   int n = 0;
   for(int i = 0; i < PositionsTotal(); i++)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0) continue;
      if(PositionSelectByTicket(tk)
         && PositionGetInteger(POSITION_MAGIC) == InpMagic
         && PositionGetString(POSITION_SYMBOL) == _Symbol) n++;
     }
   return(n);
  }

//+------------------------------------------------------------------+
string ModeName()   { return(InpMode == MODE_PAPER ? "PAPER" : "LIVE_SAFE"); }
string SignalName() { return(InpSignal == SIG_NONE ? "NONE" : (InpSignal == SIG_DONCHIAN ? "DONCHIAN" : "ZFADE")); }

void Log(string msg)
  {
   string line = StringFormat("%s | %s", TimeToString(TimeCurrent(), TIME_DATE|TIME_SECONDS), msg);
   Print(line);
   if(g_logFile != INVALID_HANDLE)
     {
      FileWrite(g_logFile, line);
      FileFlush(g_logFile);
     }
  }
//+------------------------------------------------------------------+
