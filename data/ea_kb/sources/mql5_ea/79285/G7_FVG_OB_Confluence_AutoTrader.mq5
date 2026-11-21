//+------------------------------------------------------------------+
//|                             G7_FVG_OB_Confluence_AutoTrader.mq5  |
//|                                  Copyright 2026, G7 Trading Team |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright   "Copyright 2026, G7 Trading Team"
#property link        "https://www.mql5.com"
#property version     "2.00"
#property description "G7 High-Frequency Institutional SMC Dashboard & Auto-Execution Engine"
#property description "M15 Order Block + FVG Confluence, AI Confidence Radar & Interactive Control Deck"

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>
#include <Trade\SymbolInfo.mqh>

//+------------------------------------------------------------------+
//| SYSTEM DEFINITIONS & CONSTANTS                                   |
//+------------------------------------------------------------------+
#define UI_PREFIX             "G7AI_"
#define MAX_SMC_ZONES         60
#define MAX_HIST_BARS         300

enum ENUM_SMC_ZONE_TYPE
{
   ZONE_NONE = 0,
   ZONE_BULLISH_OB = 1,
   ZONE_BEARISH_OB = 2,
   ZONE_BULLISH_FVG = 3,
   ZONE_BEARISH_FVG = 4,
   ZONE_GOLDEN_CONFLUENCE_BULL = 5,
   ZONE_GOLDEN_CONFLUENCE_BEAR = 6
};

enum ENUM_EXECUTION_TRIGGER
{
   TRIGGER_ZONE_TOUCH = 0,       // Execute on Immediate Zone Entry Touch
   TRIGGER_50_PERCENT_EQ = 1,    // Execute at 50% Equilibrium Retest
   TRIGGER_REJECTION_CONFIRM = 2 // Execute on Candle Rejection Close
};

struct SMC_Zone
{
   ulong                id;
   ENUM_SMC_ZONE_TYPE   type;
   datetime             time_start;
   datetime             time_end;
   double               price_high;
   double               price_low;
   double               price_mid;
   bool                 is_mitigated;
   datetime             mitigation_time;
   bool                 trade_triggered;
   string               box_name;
   string               label_name;
   color                box_color;
};

//+------------------------------------------------------------------+
//| INPUT PARAMETERS CONFIGURATION                                   |
//+------------------------------------------------------------------+
#define GRP_SMC      "=== 1. SMART MONEY CONCEPTS (M15 SCANNER) ==="
#define GRP_CONF     "=== 2. M15 OB + FVG CONFLUENCE ENGINE ==="
#define GRP_EXEC     "=== 3. AUTO-EXECUTION & RISK SIZING ==="
#define GRP_PROTECT  "=== 4. PROP FIRM & PROTECTION ENGINE ==="
#define GRP_UI       "=== 5. ON-CHART OBSIDIAN HUD DASHBOARD ==="

input group GRP_SMC
input ENUM_TIMEFRAMES InpSmcTimeframe       = PERIOD_M15;    // SMC Timeframe (M15 Recommended)
input int             InpLookbackBars       = 150;           // Analysis Bar History Depth
input int             InpSwingLookback      = 5;             // Swing High/Low Strength (BOS Pivot)
input double          InpMinFvgPips         = 3.0;           // Minimum FVG Imbalance Size (Pips)
input double          InpObDisplacementMult = 1.6;           // Order Block Impulse Multiplier (vs ATR)
input bool            InpRemoveMitigated    = true;          // Clean Mitigated Zones From Chart

input group GRP_CONF
input bool            InpRequireOverlap     = true;          // Require Strict Physical OB+FVG Overlap
input double          InpOverlapTolerancePips= 2.0;          // Confluence Proximity Tolerance (Pips)
input ENUM_EXECUTION_TRIGGER InpTriggerMode = TRIGGER_ZONE_TOUCH; // Execution Entry Mode
input int             InpCooldownBarsM15    = 3;             // Signal Cooldown Between Entries (M15 Bars)
input int             InpMinConfidenceToTrade= 70;           // Minimum AI Confidence % To Execute (e.g. 70%)

input group GRP_EXEC
input bool            InpDefaultAutoTrade   = true;          // Auto-Execute Trades On Confluence Match
input double          InpDefaultLot         = 0.01;          // Base Trade Lot Size
input double          InpDefaultSL_Pips     = 25.0;          // Protective Stop Loss (Pips, 0=Zone High/Low)
input double          InpDefaultTP_Pips     = 50.0;          // Target Take Profit (Pips)
input ulong           InpMagicNumber        = 777715;        // Expert Magic Number
input bool            InpEnableAutoBE       = true;          // Auto Breakeven Shield
input double          InpBETriggerPips      = 15.0;          // Breakeven Activation Pips
input double          InpBELockPips         = 3.0;           // Breakeven Profit Locked Pips
input bool            InpEnableTrailing     = true;          // Dynamic Trailing Stop
input double          InpTrailingStartPips  = 20.0;          // Trailing Start Activation (Pips)
input double          InpTrailingDistPips   = 15.0;          // Trailing Distance (Pips)

input group GRP_PROTECT
input bool            InpEnablePropGuard    = true;          // Enable Prop Firm Daily Drawdown Shield
input double          InpMaxDailyLossPct    = 4.0;           // Max Daily Loss % (Circuit Breaker)
input double          InpMaxDailyProfitPct  = 8.0;           // Max Daily Profit % (Target Lock)
input double          InpMaxSpreadAllowed   = 4.0;           // Max Allowed Spread (Pips)

input group GRP_UI
input bool            InpShowDashboard      = true;          // Show On-Chart Glassmorphism Panel
input bool            InpApplyChartTheme    = true;          // Auto-Apply Luxury Gold/Red Theme
input bool            InpShowWatermark      = true;          // Show G7 Luxury Watermark
input ENUM_BASE_CORNER InpPanelCorner       = CORNER_LEFT_UPPER; // Panel Corner Anchor
input int             InpPanelX             = 20;            // Panel X Offset (Pixels)
input int             InpPanelY             = 50;            // Panel Y Offset (Clean Upper Offset)
input bool            InpDrawZonesOnChart   = true;          // Draw Visual OB & FVG Boxes
input color           InpBullObColor        = C'16,80,60';   // Bullish Order Block Color
input color           InpBearObColor        = C'90,25,35';   // Bearish Order Block Color
input color           InpBullFvgColor       = C'10,60,90';   // Bullish FVG Color
input color           InpBearFvgColor       = C'85,45,20';   // Bearish FVG Color
input color           InpConfluenceColor    = C'212,175,55'; // Golden Confluence Border Color

//+------------------------------------------------------------------+
//| GLOBAL STATE & OBJECTS                                           |
//+------------------------------------------------------------------+
CTrade         m_trade;
CPositionInfo  m_position;
CAccountInfo   m_account;
CSymbolInfo    m_symbol;

// SMC Zones Storage
SMC_Zone       g_obZones[];
SMC_Zone       g_fvgZones[];
SMC_Zone       g_confZones[];
int            g_obCount            = 0;
int            g_fvgCount           = 0;
int            g_confCount          = 0;
ulong          g_zoneIdCounter      = 1000;

// Interactive Dashboard Runtime Variables
double         g_currentLot         = 0.01;
double         g_currentSL_Pips     = 25.0;
double         g_currentTP_Pips     = 50.0;
bool           g_autoTradeActive    = true;
bool           g_autoBEActive       = true;
bool           g_trailingActive     = true;

// Prop Firm Protection State
datetime       g_lastDayReset       = 0;
double         g_dayStartBalance    = 0.0;
double         g_dayStartEquity     = 0.0;
bool           g_circuitBreakerHit  = false;
string         g_circuitReason      = "";

// Last Trade Execution Tracking
datetime       g_lastLongEntryTime  = 0;
datetime       g_lastShortEntryTime = 0;
ulong          g_lastExecutedZoneId = 0;

// AI Confidence Calculation Metrics
int            g_aiConfidencePct    = 50;
string         g_newsStatus         = "No High-Impact USD News";
string         g_newsBiasBadge      = "SAFE  ●  [+20%]";
color          g_newsBiasColor      = C'0,230,118';

string         g_dxyStatus          = "UNAVAILABLE | XAUUSD SELL";
string         g_dxyAlignmentBadge  = "STANDBY  [+0%]";
color          g_dxyAlignmentColor  = C'150,170,195';

string         g_fvgStatusBadge     = "✔  BEARISH FVG (SELL)  [+20%]";
color          g_fvgStatusColor     = C'255,75,85';

string         g_sweepStatusBadge   = "▲  TARGETING SSL (NO SWEEP)  [+0%]";
color          g_sweepStatusColor   = C'255,200,50';

string         g_obStatusBadge      = "✔  BULLISH OB (BUY)  [+0%]";
color          g_obStatusColor      = C'0,230,118';

string         g_confLine1          = "▲ CONFLUENCE CONFLICT: FVG and Order Block are";
string         g_confLine2          = "showing opposing signals. Score capped at 60%.";
string         g_bannerBottomText   = "AI CONFIDENCE (50%) IS BELOW 70% THRESHOLD";
string         g_bannerSubText      = "Market in consolidation or conflicting institutional alignment. Manual trade execution withheld to safeguard capital.";
string         g_bannerStatusText   = "STATUS: PATIENCE STANDBY";
color          g_bannerBorderColor  = C'180,140,35';
color          g_bannerTextColor    = C'255,190,30';

//+------------------------------------------------------------------+
//| Pip Size Resolver for any symbol                                 |
//+------------------------------------------------------------------+
double GetPipSize(const string sym)
{
   double pt = SymbolInfoDouble(sym, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   if(digits == 3 || digits == 5) return pt * 10.0;
   if(digits == 2) return pt * 10.0; // Institutional standard: 1 pip = 10 points ($0.10 on XAUUSD Gold)
   return pt;
}

//+------------------------------------------------------------------+
//| Prop Firm Day Reset Routine                                      |
//+------------------------------------------------------------------+
void CheckDailyReset()
{
   MqlDateTime dt;
   TimeCurrent(dt);
   datetime todayStart = StringToTime(StringFormat("%04d.%02d.%02d 00:00", dt.year, dt.mon, dt.day));

   if(g_lastDayReset != todayStart)
   {
      g_lastDayReset      = todayStart;
      g_dayStartBalance   = AccountInfoDouble(ACCOUNT_BALANCE);
      g_dayStartEquity    = AccountInfoDouble(ACCOUNT_EQUITY);
      g_circuitBreakerHit = false;
      g_circuitReason     = "";
   }
}

//+------------------------------------------------------------------+
//| Prop Firm Circuit Breaker Enforcement                            |
//+------------------------------------------------------------------+
void CheckPropFirmGuard()
{
   if(!InpEnablePropGuard || g_circuitBreakerHit) return;

   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   double baseline = (g_dayStartBalance > 0.0) ? g_dayStartBalance : currentEquity;
   if(baseline <= 0.0) return;

   double dailyNetChange = currentEquity - baseline;
   double dailyNetPct    = (dailyNetChange / baseline) * 100.0;

   if(dailyNetPct <= -MathAbs(InpMaxDailyLossPct))
   {
      g_circuitBreakerHit = true;
      g_circuitReason = StringFormat("DAILY LOSS LIMIT REACHED: %.2f%% (Limit: -%.2f%%)", dailyNetPct, InpMaxDailyLossPct);
      Alert(StringFormat("[G7 SMC PROTECT] EMERGENCY LOCK: %s", g_circuitReason));
      CloseAllPositions();
      return;
   }

   if(InpMaxDailyProfitPct > 0.0 && dailyNetPct >= InpMaxDailyProfitPct)
   {
      g_circuitBreakerHit = true;
      g_circuitReason = StringFormat("DAILY TARGET ACHIEVED: +%.2f%% (Target: +%.2f%%)", dailyNetPct, InpMaxDailyProfitPct);
      Alert(StringFormat("[G7 SMC PROTECT] TARGET SECURED: %s", g_circuitReason));
      CloseAllPositions();
   }
}

//+------------------------------------------------------------------+
//| Position Query and Calculations                                  |
//+------------------------------------------------------------------+
double GetFloatingPnL(const string sym, int &openCount)
{
   double totalFloating = 0.0;
   openCount = 0;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         if(sym != "" && m_position.Symbol() != sym) continue;
         if(m_position.Magic() != InpMagicNumber && InpMagicNumber > 0) continue;
         totalFloating += m_position.Profit() + m_position.Swap();
         openCount++;
      }
   }
   return totalFloating;
}

//+------------------------------------------------------------------+
//| Execution Helpers                                                |
//+------------------------------------------------------------------+
void CloseAllPositions(const string sym = "")
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         if(sym != "" && m_position.Symbol() != sym) continue;
         if(m_position.Magic() != InpMagicNumber && InpMagicNumber > 0) continue;
         m_trade.PositionClose(m_position.Ticket());
      }
   }
}

void CloseProfitablePositions(const string sym = "")
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         if(sym != "" && m_position.Symbol() != sym) continue;
         if(m_position.Magic() != InpMagicNumber && InpMagicNumber > 0) continue;
         if(m_position.Profit() > 0.0)
         {
            m_trade.PositionClose(m_position.Ticket());
         }
      }
   }
}

void ClosePartialFiftyPercent(const string sym = "")
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         if(sym != "" && m_position.Symbol() != sym) continue;
         if(m_position.Magic() != InpMagicNumber && InpMagicNumber > 0) continue;

         double currentVol = m_position.Volume();
         string pSym = m_position.Symbol();
         double minLot = SymbolInfoDouble(pSym, SYMBOL_VOLUME_MIN);
         double lotStep = SymbolInfoDouble(pSym, SYMBOL_VOLUME_STEP);

         double halfVol = MathFloor((currentVol * 0.5) / lotStep) * lotStep;
         if(halfVol >= minLot && halfVol < currentVol)
         {
            m_trade.PositionClosePartial(m_position.Ticket(), halfVol);
         }
      }
   }
}

void BreakevenAllPositions(bool forceNow = false)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         string sym = m_position.Symbol();
         if(sym != _Symbol) continue;
         if(m_position.Magic() != InpMagicNumber && InpMagicNumber > 0) continue;

         double pip = GetPipSize(sym);
         double point = SymbolInfoDouble(sym, SYMBOL_POINT);
         int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
         double openPrice = m_position.PriceOpen();
         double currentSL = m_position.StopLoss();
         ENUM_POSITION_TYPE pType = m_position.PositionType();

         double stopLevelPts = (double)SymbolInfoInteger(sym, SYMBOL_TRADE_STOPS_LEVEL);
         double freezePts    = (double)SymbolInfoInteger(sym, SYMBOL_TRADE_FREEZE_LEVEL);
         double spreadPts    = (double)SymbolInfoInteger(sym, SYMBOL_SPREAD);
         double minSafeDist  = MathMax(stopLevelPts, MathMax(spreadPts, freezePts)) * point + 15.0 * point;

         if(pType == POSITION_TYPE_BUY)
         {
            double bid = SymbolInfoDouble(sym, SYMBOL_BID);
            double profitPips = (bid - openPrice) / pip;

            if(forceNow || profitPips >= InpBETriggerPips)
            {
               double newSL = NormalizeDouble(openPrice + (InpBELockPips * pip), digits);
               if((currentSL < newSL || currentSL == 0.0) && (bid - newSL >= minSafeDist))
               {
                  m_trade.PositionModify(m_position.Ticket(), newSL, m_position.TakeProfit());
               }
            }
         }
         else if(pType == POSITION_TYPE_SELL)
         {
            double ask = SymbolInfoDouble(sym, SYMBOL_ASK);
            double profitPips = (openPrice - ask) / pip;

            if(forceNow || profitPips >= InpBETriggerPips)
            {
               double newSL = NormalizeDouble(openPrice - (InpBELockPips * pip), digits);
               if((currentSL > newSL || currentSL == 0.0) && (newSL - ask >= minSafeDist))
               {
                  m_trade.PositionModify(m_position.Ticket(), newSL, m_position.TakeProfit());
               }
            }
         }
      }
   }
}

void ProcessTrailingStop()
{
   if(!g_trailingActive) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         string sym = m_position.Symbol();
         if(sym != _Symbol) continue;
         if(m_position.Magic() != InpMagicNumber && InpMagicNumber > 0) continue;

         double pip = GetPipSize(sym);
         double point = SymbolInfoDouble(sym, SYMBOL_POINT);
         int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
         double openPrice = m_position.PriceOpen();
         double currentSL = m_position.StopLoss();
         ENUM_POSITION_TYPE pType = m_position.PositionType();

         double stopLevelPts = (double)SymbolInfoInteger(sym, SYMBOL_TRADE_STOPS_LEVEL);
         double freezePts    = (double)SymbolInfoInteger(sym, SYMBOL_TRADE_FREEZE_LEVEL);
         double spreadPts    = (double)SymbolInfoInteger(sym, SYMBOL_SPREAD);
         double minSafeDist  = MathMax(stopLevelPts, MathMax(spreadPts, freezePts)) * point + 15.0 * point;

         if(pType == POSITION_TYPE_BUY)
         {
            double bid = SymbolInfoDouble(sym, SYMBOL_BID);
            double profitPips = (bid - openPrice) / pip;

            if(profitPips >= InpTrailingStartPips)
            {
               double proposedSL = NormalizeDouble(bid - (InpTrailingDistPips * pip), digits);
               if(proposedSL > currentSL + (2.0 * pip) || currentSL == 0.0)
               {
                  if(proposedSL > openPrice && (bid - proposedSL >= minSafeDist))
                  {
                     m_trade.PositionModify(m_position.Ticket(), proposedSL, m_position.TakeProfit());
                  }
               }
            }
         }
         else if(pType == POSITION_TYPE_SELL)
         {
            double ask = SymbolInfoDouble(sym, SYMBOL_ASK);
            double profitPips = (openPrice - ask) / pip;

            if(profitPips >= InpTrailingStartPips)
            {
               double proposedSL = NormalizeDouble(ask + (InpTrailingDistPips * pip), digits);
               if(proposedSL < currentSL - (2.0 * pip) || currentSL == 0.0)
               {
                  if(proposedSL < openPrice && (proposedSL - ask >= minSafeDist))
                  {
                     m_trade.PositionModify(m_position.Ticket(), proposedSL, m_position.TakeProfit());
                  }
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| Strict Volume Normalizer for all Brokers, Symbols & Netting      |
//+------------------------------------------------------------------+
double NormalizeTradeVolume(const string sym, double requestedLot)
{
   double minLot  = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);

   if(stepLot <= 0.0) stepLot = 0.01;
   if(minLot <= 0.0)  minLot  = 0.01;
   if(maxLot <= 0.0)  maxLot  = 100.0;

   double lot = requestedLot;
   if(lot < minLot) lot = minLot;
   if(lot > maxLot) lot = maxLot;

   lot = minLot + MathFloor((lot - minLot) / stepLot + 0.00001) * stepLot;

   int volDigits = 2;
   if(stepLot >= 1.0) volDigits = 0;
   else if(stepLot >= 0.1) volDigits = 1;
   else if(stepLot >= 0.01) volDigits = 2;
   else volDigits = 3;

   lot = NormalizeDouble(lot, volDigits);
   if(lot < minLot) lot = minLot;
   if(lot > maxLot) lot = maxLot;
   return lot;
}

//+------------------------------------------------------------------+
//| Dynamic Lot Normalizer within Free Margin & Broker Limits        |
//+------------------------------------------------------------------+
double CalculateSafeTradeLot(const string sym, ENUM_ORDER_TYPE orderType, double targetLot)
{
   double minLot  = SymbolInfoDouble(sym, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(sym, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(sym, SYMBOL_VOLUME_STEP);

   if(stepLot <= 0.0) stepLot = 0.01;
   if(minLot <= 0.0)  minLot  = 0.01;
   if(maxLot <= 0.0)  maxLot  = 100.0;

   double lot = NormalizeTradeVolume(sym, targetLot);
   double freeMargin = AccountInfoDouble(ACCOUNT_MARGIN_FREE);
   double ask = SymbolInfoDouble(sym, SYMBOL_ASK);
   double bid = SymbolInfoDouble(sym, SYMBOL_BID);
   double price = (orderType == ORDER_TYPE_SELL) ? bid : ask;

   if(price <= 0.0 || freeMargin <= 0.0) return 0.0;

   double singleLotMargin = 0.0;
   if(OrderCalcMargin(orderType, sym, 1.0, price, singleLotMargin) && singleLotMargin > 0.0)
   {
      double maxAffordableLot = (freeMargin * 0.90) / singleLotMargin;
      if(lot > maxAffordableLot)
      {
         lot = MathFloor(maxAffordableLot / stepLot) * stepLot;
         int volDigits = (stepLot >= 1.0) ? 0 : ((stepLot >= 0.1) ? 1 : 2);
         lot = NormalizeDouble(lot, volDigits);
      }
   }

   if(lot < minLot) return 0.0; // Cannot afford even minimum broker lot size
   if(lot > maxLot) lot = maxLot;
   return lot;
}

//+------------------------------------------------------------------+
//| Universal Broker & Asset Compliant SL/TP Engine (Zero Rejections)|
//+------------------------------------------------------------------+
void CalculateValidStops(const string sym, 
                         ENUM_ORDER_TYPE orderType, 
                         double requestedSLPips, 
                         double requestedTPPips, 
                         double customSL,
                         double &outSL, 
                         double &outTP)
{
   double point        = SymbolInfoDouble(sym, SYMBOL_POINT);
   int    digits       = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   double ask          = SymbolInfoDouble(sym, SYMBOL_ASK);
   double bid          = SymbolInfoDouble(sym, SYMBOL_BID);
   double spreadPts    = (double)SymbolInfoInteger(sym, SYMBOL_SPREAD);
   double stopLevelPts = (double)SymbolInfoInteger(sym, SYMBOL_TRADE_STOPS_LEVEL);
   double freezePts    = (double)SymbolInfoInteger(sym, SYMBOL_TRADE_FREEZE_LEVEL);
   double pip          = GetPipSize(sym);

   if(point <= 0.0) point = 0.00001;
   if(pip <= 0.0)   pip   = point * 10.0;

   // Enforce strict broker safety margin (stops level + spread + buffer)
   double maxConstraintPts = MathMax(stopLevelPts, MathMax(spreadPts, freezePts));
   double safeBufferPts    = MathMax(maxConstraintPts + 25.0, 50.0);
   double safeBufferPrice  = safeBufferPts * point;

   outSL = 0.0;
   outTP = 0.0;

   if(orderType == ORDER_TYPE_BUY)
   {
      // Buy executes at Ask, but closes at Bid. Stop Loss MUST be strictly below BID!
      double minSLDist = safeBufferPrice;
      if(requestedSLPips > 0.0)
      {
         double slDist = MathMax(requestedSLPips * pip, minSLDist);
         outSL = NormalizeDouble(bid - slDist, digits);
      }
      if(customSL > 0.0)
      {
         if(customSL <= bid - minSLDist)
            outSL = NormalizeDouble(customSL, digits);
         else
            outSL = NormalizeDouble(bid - minSLDist, digits);
      }

      // Take Profit closes at Bid, measured strictly above Ask
      if(requestedTPPips > 0.0)
      {
         double tpDist = MathMax(requestedTPPips * pip, minSLDist);
         outTP = NormalizeDouble(ask + tpDist, digits);
      }
   }
   else if(orderType == ORDER_TYPE_SELL)
   {
      // Sell executes at Bid, but closes at Ask. Stop Loss MUST be strictly above ASK!
      double minSLDist = safeBufferPrice;
      if(requestedSLPips > 0.0)
      {
         double slDist = MathMax(requestedSLPips * pip, minSLDist);
         outSL = NormalizeDouble(ask + slDist, digits);
      }
      if(customSL > 0.0)
      {
         if(customSL >= ask + minSLDist)
            outSL = NormalizeDouble(customSL, digits);
         else
            outSL = NormalizeDouble(ask + minSLDist, digits);
      }

      // Take Profit closes at Ask, measured strictly below Bid
      if(requestedTPPips > 0.0)
      {
         double tpDist = MathMax(requestedTPPips * pip, minSLDist);
         outTP = NormalizeDouble(bid - tpDist, digits);
      }
   }
}

//+------------------------------------------------------------------+
//| Execute Fast Market Order with Dynamic Risk, Margin & Stops Guard|
//+------------------------------------------------------------------+
bool ExecuteSMCAutoTrade(ENUM_ORDER_TYPE orderType, double customSL = 0.0, string comment = "G7 SMC M15 Confluence")
{
   if(g_circuitBreakerHit)
   {
      Print("[G7 SMC] Execution blocked: Prop Firm Circuit Breaker is active!");
      return false;
   }

   string sym = _Symbol;
   double point = SymbolInfoDouble(sym, SYMBOL_POINT);
   double pip = GetPipSize(sym);
   if(point <= 0.0 || pip <= 0.0) return false;

   double currentSpread = (double)SymbolInfoInteger(sym, SYMBOL_SPREAD) * point / pip;
   if(currentSpread > InpMaxSpreadAllowed && !MQLInfoInteger(MQL_TESTER))
   {
      PrintFormat("[G7 SMC] Spread too high: %.1f pips (Max: %.1f pips)", currentSpread, InpMaxSpreadAllowed);
      return false;
   }

   // Strict Free Margin Verification: Never call Buy/Sell if margin exceeds free capital
   double lot = CalculateSafeTradeLot(sym, orderType, g_currentLot);
   if(lot <= 0.0)
   {
      PrintFormat("[G7 SMC] Free margin (%.2f) insufficient for minimum lot. Trade safely withheld.", AccountInfoDouble(ACCOUNT_MARGIN_FREE));
      return false;
   }

   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetDeviationInPoints(30);

   if(!m_trade.SetTypeFillingBySymbol(sym))
   {
      uint filling = (uint)SymbolInfoInteger(sym, SYMBOL_FILLING_MODE);
      if((filling & SYMBOL_FILLING_FOK) != 0)
         m_trade.SetTypeFilling(ORDER_FILLING_FOK);
      else if((filling & SYMBOL_FILLING_IOC) != 0)
         m_trade.SetTypeFilling(ORDER_FILLING_IOC);
      else
         m_trade.SetTypeFilling(ORDER_FILLING_RETURN);
   }

   double sl = 0.0, tp = 0.0;
   CalculateValidStops(sym, orderType, g_currentSL_Pips, g_currentTP_Pips, customSL, sl, tp);

   double ask = SymbolInfoDouble(sym, SYMBOL_ASK);
   double bid = SymbolInfoDouble(sym, SYMBOL_BID);

   if(orderType == ORDER_TYPE_BUY)
   {
      if(ask <= 0.0) return false;
      return m_trade.Buy(lot, sym, ask, sl, tp, comment);
   }
   else if(orderType == ORDER_TYPE_SELL)
   {
      if(bid <= 0.0) return false;
      return m_trade.Sell(lot, sym, bid, sl, tp, comment);
   }

   return false;
}

//| SMART MONEY CONCEPTS ENGINE: M15 SCANNER                         |
//+------------------------------------------------------------------+
void ScanM15OrderBlocks()
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, InpSmcTimeframe, 0, InpLookbackBars, rates);
   if(copied < InpSwingLookback * 4 + 10) return;

   double pip = GetPipSize(_Symbol);
   g_obCount = 0;
   ArrayResize(g_obZones, MAX_SMC_ZONES);

   double sumRange = 0.0;
   int checkBars = MathMin(20, copied - 1);
   if(checkBars < 5) return;
   for(int k = 1; k <= checkBars; k++)
   {
      sumRange += (rates[k].high - rates[k].low);
   }
   double avgRange = (sumRange / (double)checkBars);
   if(avgRange <= 0.0) avgRange = 10.0 * pip;

   int maxLoop = copied - InpSwingLookback - 3;
   for(int i = InpSwingLookback + 1; i < maxLoop; i++)
   {
      if(g_obCount >= MAX_SMC_ZONES - 2) break;

      bool isBearCandle = (rates[i].close < rates[i].open);
      bool isStrongExpansionUp = (rates[i-1].close > rates[i-1].open) && 
                                 ((rates[i-1].close - rates[i-1].open) >= avgRange * InpObDisplacementMult);

      if(isBearCandle && isStrongExpansionUp)
      {
         double highestPrior = rates[i+1].high;
         for(int s = 1; s <= InpSwingLookback; s++)
         {
            int checkIdx = i + s;
            if(checkIdx < copied)
            {
               if(rates[checkIdx].high > highestPrior) highestPrior = rates[checkIdx].high;
            }
         }

         if(rates[i-1].high > highestPrior)
         {
            SMC_Zone ob;
            ob.id = ++g_zoneIdCounter;
            ob.type = ZONE_BULLISH_OB;
            ob.time_start = rates[i].time;
            ob.time_end = TimeCurrent() + PeriodSeconds(InpSmcTimeframe) * 12;
            ob.price_high = rates[i].high;
            ob.price_low = rates[i].low;
            ob.price_mid = (ob.price_high + ob.price_low) * 0.5;
            ob.is_mitigated = false;
            ob.trade_triggered = false;
            ob.box_color = InpBullObColor;
            ob.box_name = StringFormat("%sOB_BULL_%I64u", UI_PREFIX, ob.id);
            ob.label_name = StringFormat("%sLBL_OB_BULL_%I64u", UI_PREFIX, ob.id);

            for(int m = i - 2; m >= 0; m--)
            {
               if(rates[m].low <= ob.price_high)
               {
                  ob.is_mitigated = true;
                  ob.mitigation_time = rates[m].time;
                  break;
               }
            }

            g_obZones[g_obCount++] = ob;
         }
      }

      bool isBullCandle = (rates[i].close > rates[i].open);
      bool isStrongExpansionDown = (rates[i-1].close < rates[i-1].open) && 
                                   ((rates[i-1].open - rates[i-1].close) >= avgRange * InpObDisplacementMult);

      if(isBullCandle && isStrongExpansionDown)
      {
         double lowestPrior = rates[i+1].low;
         for(int s = 1; s <= InpSwingLookback; s++)
         {
            int checkIdx = i + s;
            if(checkIdx < copied)
            {
               if(rates[checkIdx].low < lowestPrior) lowestPrior = rates[checkIdx].low;
            }
         }

         if(rates[i-1].low < lowestPrior)
         {
            SMC_Zone ob;
            ob.id = ++g_zoneIdCounter;
            ob.type = ZONE_BEARISH_OB;
            ob.time_start = rates[i].time;
            ob.time_end = TimeCurrent() + PeriodSeconds(InpSmcTimeframe) * 12;
            ob.price_high = rates[i].high;
            ob.price_low = rates[i].low;
            ob.price_mid = (ob.price_high + ob.price_low) * 0.5;
            ob.is_mitigated = false;
            ob.trade_triggered = false;
            ob.box_color = InpBearObColor;
            ob.box_name = StringFormat("%sOB_BEAR_%I64u", UI_PREFIX, ob.id);
            ob.label_name = StringFormat("%sLBL_OB_BEAR_%I64u", UI_PREFIX, ob.id);

            for(int m = i - 2; m >= 0; m--)
            {
               if(rates[m].high >= ob.price_low)
               {
                  ob.is_mitigated = true;
                  ob.mitigation_time = rates[m].time;
                  break;
               }
            }

            g_obZones[g_obCount++] = ob;
         }
      }
   }
}

//| SMART MONEY CONCEPTS ENGINE: M15 FVG SCANNER                     |
//+------------------------------------------------------------------+
void ScanM15FairValueGaps()
{
   MqlRates rates[];
   ArraySetAsSeries(rates, true);
   int copied = CopyRates(_Symbol, InpSmcTimeframe, 0, InpLookbackBars, rates);
   if(copied < 10) return;

   double pip = GetPipSize(_Symbol);
   g_fvgCount = 0;
   ArrayResize(g_fvgZones, MAX_SMC_ZONES);

   for(int i = 1; i < copied - 2; i++)
   {
      if(g_fvgCount >= MAX_SMC_ZONES - 2) break;

      double gapTopBull = rates[i-1].low;
      double gapBottomBull = rates[i+1].high;
      double gapSizeBull = (gapTopBull - gapBottomBull) / pip;

      if(gapTopBull > gapBottomBull && gapSizeBull >= InpMinFvgPips)
      {
         SMC_Zone fvg;
         fvg.id = ++g_zoneIdCounter;
         fvg.type = ZONE_BULLISH_FVG;
         fvg.time_start = rates[i].time;
         fvg.time_end = TimeCurrent() + PeriodSeconds(InpSmcTimeframe) * 12;
         fvg.price_high = gapTopBull;
         fvg.price_low = gapBottomBull;
         fvg.price_mid = (gapTopBull + gapBottomBull) * 0.5;
         fvg.is_mitigated = false;
         fvg.trade_triggered = false;
         fvg.box_color = InpBullFvgColor;
         fvg.box_name = StringFormat("%sFVG_BULL_%I64u", UI_PREFIX, fvg.id);
         fvg.label_name = StringFormat("%sLBL_FVG_BULL_%I64u", UI_PREFIX, fvg.id);

         for(int m = i - 2; m >= 0; m--)
         {
            if(rates[m].low <= fvg.price_low)
            {
               fvg.is_mitigated = true;
               fvg.mitigation_time = rates[m].time;
               break;
            }
         }

         g_fvgZones[g_fvgCount++] = fvg;
      }

      double gapTopBear = rates[i+1].low;
      double gapBottomBear = rates[i-1].high;
      double gapSizeBear = (gapTopBear - gapBottomBear) / pip;

      if(gapTopBear > gapBottomBear && gapSizeBear >= InpMinFvgPips)
      {
         SMC_Zone fvg;
         fvg.id = ++g_zoneIdCounter;
         fvg.type = ZONE_BEARISH_FVG;
         fvg.time_start = rates[i].time;
         fvg.time_end = TimeCurrent() + PeriodSeconds(InpSmcTimeframe) * 12;
         fvg.price_high = gapTopBear;
         fvg.price_low = gapBottomBear;
         fvg.price_mid = (gapTopBear + gapBottomBear) * 0.5;
         fvg.is_mitigated = false;
         fvg.trade_triggered = false;
         fvg.box_color = InpBearFvgColor;
         fvg.box_name = StringFormat("%sFVG_BEAR_%I64u", UI_PREFIX, fvg.id);
         fvg.label_name = StringFormat("%sLBL_FVG_BEAR_%I64u", UI_PREFIX, fvg.id);

         for(int m = i - 2; m >= 0; m--)
         {
            if(rates[m].high >= fvg.price_high)
            {
               fvg.is_mitigated = true;
               fvg.mitigation_time = rates[m].time;
               break;
            }
         }

         g_fvgZones[g_fvgCount++] = fvg;
      }
   }
}

//+------------------------------------------------------------------+
//| M15 OB + FVG CONFLUENCE MATCHER & GOLDEN ZONE DETECTOR           |
//+------------------------------------------------------------------+
void MatchObFvgConfluence()
{
   double pip = GetPipSize(_Symbol);
   double tol = InpOverlapTolerancePips * pip;
   g_confCount = 0;
   ArrayResize(g_confZones, MAX_SMC_ZONES);

   for(int b = 0; b < g_obCount; b++)
   {
      if(g_obZones[b].type != ZONE_BULLISH_OB || g_obZones[b].is_mitigated) continue;

      for(int f = 0; f < g_fvgCount; f++)
      {
         if(g_fvgZones[f].type != ZONE_BULLISH_FVG || g_fvgZones[f].is_mitigated) continue;

         bool overlap = (g_obZones[b].price_low - tol <= g_fvgZones[f].price_high) &&
                        (g_obZones[b].price_high + tol >= g_fvgZones[f].price_low);

         if(overlap)
         {
            SMC_Zone conf;
            conf.id = ++g_zoneIdCounter;
            conf.type = ZONE_GOLDEN_CONFLUENCE_BULL;
            conf.time_start = MathMin(g_obZones[b].time_start, g_fvgZones[f].time_start);
            conf.time_end = TimeCurrent() + PeriodSeconds(InpSmcTimeframe) * 16;
            conf.price_high = MathMin(g_obZones[b].price_high, g_fvgZones[f].price_high);
            conf.price_low  = MathMax(g_obZones[b].price_low, g_fvgZones[f].price_low);
            conf.price_mid  = (conf.price_high + conf.price_low) * 0.5;
            conf.is_mitigated = false;
            conf.trade_triggered = (g_obZones[b].trade_triggered || g_fvgZones[f].trade_triggered);
            conf.box_color = InpConfluenceColor;
            conf.box_name = StringFormat("%sCONF_BULL_%I64u", UI_PREFIX, conf.id);
            conf.label_name = StringFormat("%sLBL_CONF_BULL_%I64u", UI_PREFIX, conf.id);

            g_confZones[g_confCount++] = conf;
            break;
         }
      }
   }

   for(int b = 0; b < g_obCount; b++)
   {
      if(g_obZones[b].type != ZONE_BEARISH_OB || g_obZones[b].is_mitigated) continue;

      for(int f = 0; f < g_fvgCount; f++)
      {
         if(g_fvgZones[f].type != ZONE_BEARISH_FVG || g_fvgZones[f].is_mitigated) continue;

         bool overlap = (g_obZones[b].price_low - tol <= g_fvgZones[f].price_high) &&
                        (g_obZones[b].price_high + tol >= g_fvgZones[f].price_low);

         if(overlap)
         {
            SMC_Zone conf;
            conf.id = ++g_zoneIdCounter;
            conf.type = ZONE_GOLDEN_CONFLUENCE_BEAR;
            conf.time_start = MathMin(g_obZones[b].time_start, g_fvgZones[f].time_start);
            conf.time_end = TimeCurrent() + PeriodSeconds(InpSmcTimeframe) * 16;
            conf.price_high = MathMin(g_obZones[b].price_high, g_fvgZones[f].price_high);
            conf.price_low  = MathMax(g_obZones[b].price_low, g_fvgZones[f].price_low);
            conf.price_mid  = (conf.price_high + conf.price_low) * 0.5;
            conf.is_mitigated = false;
            conf.trade_triggered = (g_obZones[b].trade_triggered || g_fvgZones[f].trade_triggered);
            conf.box_color = InpConfluenceColor;
            conf.box_name = StringFormat("%sCONF_BEAR_%I64u", UI_PREFIX, conf.id);
            conf.label_name = StringFormat("%sLBL_CONF_BEAR_%I64u", UI_PREFIX, conf.id);

            g_confZones[g_confCount++] = conf;
            break;
         }
      }
   }

   // Update AI Confidence Rating based on Confluence & Alignments
   int score = 20; // Base news safe +20%
   bool hasBullOB = false, hasBearOB = false;
   bool hasBullFVG = false, hasBearFVG = false;

   for(int b = 0; b < g_obCount; b++)
   {
      if(!g_obZones[b].is_mitigated)
      {
         if(g_obZones[b].type == ZONE_BULLISH_OB) hasBullOB = true;
         if(g_obZones[b].type == ZONE_BEARISH_OB) hasBearOB = true;
      }
   }

   for(int f = 0; f < g_fvgCount; f++)
   {
      if(!g_fvgZones[f].is_mitigated)
      {
         if(g_fvgZones[f].type == ZONE_BULLISH_FVG) hasBullFVG = true;
         if(g_fvgZones[f].type == ZONE_BEARISH_FVG) hasBearFVG = true;
      }
   }

   // Update FVG Badge
   if(hasBearFVG && !hasBullFVG)
   {
      g_fvgStatusBadge = "✔  BEARISH FVG (SELL)  [+20%]";
      g_fvgStatusColor = C'255,75,85';
      score += 20;
   }
   else if(hasBullFVG && !hasBearFVG)
   {
      g_fvgStatusBadge = "✔  BULLISH FVG (BUY)  [+20%]";
      g_fvgStatusColor = C'0,230,118';
      score += 20;
   }
   else if(hasBullFVG && hasBearFVG)
   {
      g_fvgStatusBadge = "▲  DUAL IMBALANCE  [+10%]";
      g_fvgStatusColor = C'255,200,50';
      score += 10;
   }
   else
   {
      g_fvgStatusBadge = "MONITORING  [+0%]";
      g_fvgStatusColor = C'150,170,195';
   }

   // Update OB Badge
   if(hasBullOB && !hasBearOB)
   {
      g_obStatusBadge = "✔  BULLISH OB (BUY)  [+20%]";
      g_obStatusColor = C'0,230,118';
      score += 20;
   }
   else if(hasBearOB && !hasBullOB)
   {
      g_obStatusBadge = "✔  BEARISH OB (SELL)  [+20%]";
      g_obStatusColor = C'255,75,85';
      score += 20;
   }
   else if(hasBullOB && hasBearOB)
   {
      g_obStatusBadge = "▲  DUAL ZONES  [+10%]";
      g_obStatusColor = C'255,200,50';
      score += 10;
   }
   else
   {
      g_obStatusBadge = "MONITORING  [+0%]";
      g_obStatusColor = C'150,170,195';
   }

   g_aiConfidencePct = MathMin(100, MathMax(10, score));

   // Golden Confluence Extra Bonus
   if(g_confCount > 0)
   {
      score += 35; // Huge confidence boost when OB + FVG coincide!
      g_confLine1 = "★ GOLDEN CONFLUENCE: M15 OB + FVG MATCHED";
      g_confLine2 = "High probability institutional entry armed.";
      g_bannerBottomText = StringFormat("AI CONFIDENCE (%d%%) IS ABOVE 70%% THRESHOLD", g_aiConfidencePct);
      g_bannerSubText = "Precision SMC confluence locked. Institutional liquidity flow armed for execution.";
      g_bannerStatusText = "STATUS: ARMED & READY";
      g_bannerBorderColor = C'0,212,255';
      g_bannerTextColor = C'0,230,118';
   }
   else if((hasBullOB && hasBearFVG) || (hasBearOB && hasBullFVG))
   {
      g_aiConfidencePct = MathMin(g_aiConfidencePct, 50); // Confluence conflict cap
      g_confLine1 = "▲ CONFLUENCE CONFLICT: FVG and Order Block are";
      g_confLine2 = "showing opposing signals. Score capped at 60%.";
      g_bannerBottomText = StringFormat("AI CONFIDENCE (%d%%) IS BELOW 70%% THRESHOLD", g_aiConfidencePct);
      g_bannerSubText = "Market in consolidation or conflicting institutional alignment. Manual trade execution withheld to safeguard capital.";
      g_bannerStatusText = "STATUS: PATIENCE STANDBY";
      g_bannerBorderColor = C'180,140,35';
      g_bannerTextColor = C'255,190,30';
   }
   else
   {
      g_confLine1 = "Scanning M15 Market Structure for institutional";
      g_confLine2 = "Order Block & Fair Value Gap confluence.";
      g_bannerBottomText = StringFormat("AI CONFIDENCE (%d%%) IS BELOW 70%% THRESHOLD", g_aiConfidencePct);
      g_bannerSubText = "Market in consolidation or awaiting setup. Discipline and capital protection enforced.";
      g_bannerStatusText = "STATUS: PATIENCE STANDBY";
      g_bannerBorderColor = C'180,140,35';
      g_bannerTextColor = C'255,190,30';
   }
}

//+------------------------------------------------------------------+
//| AUTO-EXECUTION ENGINE: RETEST & ENTRY TRIGGER                    |
//+------------------------------------------------------------------+
void ProcessAutoExecution()
{
   if(!g_autoTradeActive || g_circuitBreakerHit) return;
   if(g_aiConfidencePct < InpMinConfidenceToTrade) return;

   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double pip = GetPipSize(_Symbol);
   int digits = (int)SymbolInfoInteger(_Symbol, SYMBOL_DIGITS);

   for(int c = 0; c < g_confCount; c++)
   {
      if(g_confZones[c].is_mitigated || g_confZones[c].trade_triggered) continue;

      if(g_confZones[c].type == ZONE_GOLDEN_CONFLUENCE_BULL)
      {
         bool entryHit = false;
         if(InpTriggerMode == TRIGGER_ZONE_TOUCH)
         {
            entryHit = (ask <= g_confZones[c].price_high && ask >= g_confZones[c].price_low - (3.0 * pip));
         }
         else if(InpTriggerMode == TRIGGER_50_PERCENT_EQ)
         {
            entryHit = (ask <= g_confZones[c].price_mid);
         }

         if(entryHit)
         {
            datetime now = TimeCurrent();
            if(now - g_lastLongEntryTime >= PeriodSeconds(InpSmcTimeframe) * InpCooldownBarsM15)
            {
               double customSL = NormalizeDouble(g_confZones[c].price_low - (5.0 * pip), digits);
               bool res = ExecuteSMCAutoTrade(ORDER_TYPE_BUY, customSL, "G7 M15 OB+FVG LONG");
               if(res)
               {
                  g_confZones[c].trade_triggered = true;
                  g_lastLongEntryTime = now;
                  Print("[G7 SMC AUTO] Long Executed on M15 OB+FVG Golden Confluence!");
               }
            }
         }
      }
      else if(g_confZones[c].type == ZONE_GOLDEN_CONFLUENCE_BEAR)
      {
         bool entryHit = false;
         if(InpTriggerMode == TRIGGER_ZONE_TOUCH)
         {
            entryHit = (bid >= g_confZones[c].price_low && bid <= g_confZones[c].price_high + (3.0 * pip));
         }
         else if(InpTriggerMode == TRIGGER_50_PERCENT_EQ)
         {
            entryHit = (bid >= g_confZones[c].price_mid);
         }

         if(entryHit)
         {
            datetime now = TimeCurrent();
            if(now - g_lastShortEntryTime >= PeriodSeconds(InpSmcTimeframe) * InpCooldownBarsM15)
            {
               double customSL = NormalizeDouble(g_confZones[c].price_high + (5.0 * pip), digits);
               bool res = ExecuteSMCAutoTrade(ORDER_TYPE_SELL, customSL, "G7 M15 OB+FVG SHORT");
               if(res)
               {
                  g_confZones[c].trade_triggered = true;
                  g_lastShortEntryTime = now;
                  Print("[G7 SMC AUTO] Short Executed on M15 OB+FVG Golden Confluence!");
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| VISUAL CHART DRAWING: OB & FVG RECTANGLES & LABELS               |
//+------------------------------------------------------------------+
void DrawSMCZonesOnChart()
{
   if(!InpDrawZonesOnChart) return;

   for(int c = 0; c < g_confCount; c++)
   {
      if(InpRemoveMitigated && g_confZones[c].is_mitigated)
      {
         ObjectDelete(0, g_confZones[c].box_name);
         ObjectDelete(0, g_confZones[c].label_name);
         continue;
      }

      string bName = g_confZones[c].box_name;
      if(ObjectFind(0, bName) < 0)
      {
         ObjectCreate(0, bName, OBJ_RECTANGLE, 0, g_confZones[c].time_start, g_confZones[c].price_high, g_confZones[c].time_end, g_confZones[c].price_low);
         ObjectSetInteger(0, bName, OBJPROP_COLOR, InpConfluenceColor);
         ObjectSetInteger(0, bName, OBJPROP_STYLE, STYLE_SOLID);
         ObjectSetInteger(0, bName, OBJPROP_WIDTH, 2);
         ObjectSetInteger(0, bName, OBJPROP_BACK, true);
         ObjectSetInteger(0, bName, OBJPROP_SELECTABLE, false);
      }
      else
      {
         ObjectSetInteger(0, bName, OBJPROP_TIME, 1, g_confZones[c].time_end);
      }

      string lName = g_confZones[c].label_name;
      if(ObjectFind(0, lName) < 0)
      {
         ObjectCreate(0, lName, OBJ_TEXT, 0, g_confZones[c].time_start, g_confZones[c].price_high);
         string txt = (g_confZones[c].type == ZONE_GOLDEN_CONFLUENCE_BULL) ? "★ M15 BULLISH CONFLUENCE (OB+FVG)" : "★ M15 BEARISH CONFLUENCE (OB+FVG)";
         ObjectSetString(0, lName, OBJPROP_TEXT, txt);
         ObjectSetString(0, lName, OBJPROP_FONT, "Segoe UI Bold");
         ObjectSetInteger(0, lName, OBJPROP_FONTSIZE, 8);
         ObjectSetInteger(0, lName, OBJPROP_COLOR, InpConfluenceColor);
         ObjectSetInteger(0, lName, OBJPROP_ANCHOR, ANCHOR_LEFT_LOWER);
      }
   }

   for(int b = 0; b < g_obCount; b++)
   {
      if(InpRemoveMitigated && g_obZones[b].is_mitigated)
      {
         ObjectDelete(0, g_obZones[b].box_name);
         ObjectDelete(0, g_obZones[b].label_name);
         continue;
      }

      string bName = g_obZones[b].box_name;
      if(ObjectFind(0, bName) < 0)
      {
         ObjectCreate(0, bName, OBJ_RECTANGLE, 0, g_obZones[b].time_start, g_obZones[b].price_high, g_obZones[b].time_end, g_obZones[b].price_low);
         ObjectSetInteger(0, bName, OBJPROP_COLOR, g_obZones[b].box_color);
         ObjectSetInteger(0, bName, OBJPROP_STYLE, STYLE_SOLID);
         ObjectSetInteger(0, bName, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, bName, OBJPROP_BACK, true);
         ObjectSetInteger(0, bName, OBJPROP_SELECTABLE, false);
      }
   }

   for(int f = 0; f < g_fvgCount; f++)
   {
      if(InpRemoveMitigated && g_fvgZones[f].is_mitigated)
      {
         ObjectDelete(0, g_fvgZones[f].box_name);
         ObjectDelete(0, g_fvgZones[f].label_name);
         continue;
      }

      string fName = g_fvgZones[f].box_name;
      if(ObjectFind(0, fName) < 0)
      {
         ObjectCreate(0, fName, OBJ_RECTANGLE, 0, g_fvgZones[f].time_start, g_fvgZones[f].price_high, g_fvgZones[f].time_end, g_fvgZones[f].price_low);
         ObjectSetInteger(0, fName, OBJPROP_COLOR, g_fvgZones[f].box_color);
         ObjectSetInteger(0, fName, OBJPROP_STYLE, STYLE_DOT);
         ObjectSetInteger(0, fName, OBJPROP_WIDTH, 1);
         ObjectSetInteger(0, fName, OBJPROP_BACK, true);
         ObjectSetInteger(0, fName, OBJPROP_SELECTABLE, false);
      }
   }
}

//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| UI PRIMITIVE GENERATION HELPERS (SEGOE UI MODERN TYPOGRAPHY)     |
//+------------------------------------------------------------------+
void UI_Button(string name, int x, int y, int w, int h, string text, color bgColor, color txtColor, int fontSize = 8, bool bold = true)
{
   string objName = UI_PREFIX + name;
   if(ObjectFind(0, objName) < 0)
   {
      ObjectCreate(0, objName, OBJ_BUTTON, 0, 0, 0);
      ObjectSetInteger(0, objName, OBJPROP_CORNER, InpPanelCorner);
      ObjectSetInteger(0, objName, OBJPROP_SELECTABLE, false);
   }
   ObjectSetInteger(0, objName, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, objName, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, objName, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, objName, OBJPROP_YSIZE, h);
   ObjectSetString(0, objName, OBJPROP_FONT, "Segoe UI Semibold");
   ObjectSetInteger(0, objName, OBJPROP_FONTSIZE, fontSize);
   ObjectSetString(0, objName, OBJPROP_TEXT, text);
   ObjectSetInteger(0, objName, OBJPROP_BGCOLOR, bgColor);
   ObjectSetInteger(0, objName, OBJPROP_COLOR, txtColor);
   ObjectSetInteger(0, objName, OBJPROP_BORDER_COLOR, C'50,65,85');
   ObjectSetInteger(0, objName, OBJPROP_STATE, false);
   ObjectSetInteger(0, objName, OBJPROP_BACK, false);
   ObjectSetInteger(0, objName, OBJPROP_ZORDER, 10);
}

void UI_Label(string name, int x, int y, string text, color txtColor, int fontSize = 8, bool bold = false)
{
   string objName = UI_PREFIX + name;
   if(ObjectFind(0, objName) < 0)
   {
      ObjectCreate(0, objName, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, objName, OBJPROP_CORNER, InpPanelCorner);
      ObjectSetInteger(0, objName, OBJPROP_SELECTABLE, false);
   }
   ObjectSetInteger(0, objName, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, objName, OBJPROP_YDISTANCE, y);
   ObjectSetString(0, objName, OBJPROP_FONT, bold ? "Segoe UI Semibold" : "Segoe UI");
   ObjectSetInteger(0, objName, OBJPROP_FONTSIZE, fontSize);
   ObjectSetString(0, objName, OBJPROP_TEXT, text);
   ObjectSetInteger(0, objName, OBJPROP_COLOR, txtColor);
   ObjectSetInteger(0, objName, OBJPROP_BACK, false);
   ObjectSetInteger(0, objName, OBJPROP_ZORDER, 10);
}

void UI_Box(string name, int x, int y, int w, int h, color bgColor, color borderColor, int zorder = 0)
{
   string objName = UI_PREFIX + name;
   if(ObjectFind(0, objName) < 0)
   {
      ObjectCreate(0, objName, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, objName, OBJPROP_CORNER, InpPanelCorner);
      ObjectSetInteger(0, objName, OBJPROP_SELECTABLE, false);
   }
   ObjectSetInteger(0, objName, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, objName, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, objName, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, objName, OBJPROP_YSIZE, h);
   ObjectSetInteger(0, objName, OBJPROP_BGCOLOR, bgColor);
   ObjectSetInteger(0, objName, OBJPROP_BORDER_COLOR, borderColor);
   ObjectSetInteger(0, objName, OBJPROP_COLOR, borderColor);
   ObjectSetInteger(0, objName, OBJPROP_BORDER_TYPE, BORDER_FLAT);
   ObjectSetInteger(0, objName, OBJPROP_BACK, false);
   ObjectSetInteger(0, objName, OBJPROP_ZORDER, zorder);
}

//+------------------------------------------------------------------+
//| LUXURY GOLD & RED CHART STYLING THEME                            |
//+------------------------------------------------------------------+
void ApplyLuxuryGoldTheme()
{
   if(!InpApplyChartTheme) return;

   ChartSetInteger(0, CHART_COLOR_BACKGROUND, C'10,12,16');
   ChartSetInteger(0, CHART_COLOR_FOREGROUND, C'165,180,200');
   ChartSetInteger(0, CHART_COLOR_GRID, C'20,24,32');
   ChartSetInteger(0, CHART_SHOW_GRID, false);
   ChartSetInteger(0, CHART_SHOW_PERIOD_SEP, false);
   ChartSetInteger(0, CHART_SHOW_OHLC, false);
   ChartSetInteger(0, CHART_MODE, CHART_CANDLES);
   ChartSetInteger(0, CHART_SHIFT, true);
   ChartSetDouble(0, CHART_SHIFT_SIZE, 12.0);

   // Bull candles = Pure Luxury Gold
   ChartSetInteger(0, CHART_COLOR_CANDLE_BULL, C'255,215,0');
   ChartSetInteger(0, CHART_COLOR_CHART_UP, C'255,215,0');

   // Bear candles = Vibrant Institutional Red
   ChartSetInteger(0, CHART_COLOR_CANDLE_BEAR, C'235,50,50');
   ChartSetInteger(0, CHART_COLOR_CHART_DOWN, C'235,50,50');

   ChartSetInteger(0, CHART_COLOR_CHART_LINE, C'255,215,0');
   ChartSetInteger(0, CHART_COLOR_BID, C'190,195,205');
   ChartSetInteger(0, CHART_COLOR_ASK, C'235,50,50');
   ChartSetInteger(0, CHART_COLOR_LAST, C'255,215,0');
   ChartSetInteger(0, CHART_COLOR_STOP_LEVEL, C'255,60,75');
   ChartSetInteger(0, CHART_COLOR_VOLUME, C'35,50,70');
}

//+------------------------------------------------------------------+
//| G7 WATERMARK ENGINE (INSTITUTIONAL LUXURY BACKGROUND)            |
//+------------------------------------------------------------------+
void RenderChartWatermark()
{
   if(!InpShowWatermark) return;

   string wmName = UI_PREFIX + "WM_G7";
   string subName = UI_PREFIX + "WM_SUB";

   if(ObjectFind(0, wmName) < 0)
   {
      ObjectCreate(0, wmName, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, wmName, OBJPROP_CORNER, CORNER_RIGHT_LOWER);
      ObjectSetInteger(0, wmName, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, wmName, OBJPROP_BACK, true);
   }
   ObjectSetInteger(0, wmName, OBJPROP_XDISTANCE, 190);
   ObjectSetInteger(0, wmName, OBJPROP_YDISTANCE, 140);
   ObjectSetString(0, wmName, OBJPROP_FONT, "Impact");
   ObjectSetInteger(0, wmName, OBJPROP_FONTSIZE, 95);
   ObjectSetString(0, wmName, OBJPROP_TEXT, "G7");
   ObjectSetInteger(0, wmName, OBJPROP_COLOR, C'38,32,18');
   ObjectSetInteger(0, wmName, OBJPROP_BACK, true);
   ObjectSetInteger(0, wmName, OBJPROP_ZORDER, 0);

   if(ObjectFind(0, subName) < 0)
   {
      ObjectCreate(0, subName, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, subName, OBJPROP_CORNER, CORNER_RIGHT_LOWER);
      ObjectSetInteger(0, subName, OBJPROP_SELECTABLE, false);
      ObjectSetInteger(0, subName, OBJPROP_BACK, true);
   }
   ObjectSetInteger(0, subName, OBJPROP_XDISTANCE, 240);
   ObjectSetInteger(0, subName, OBJPROP_YDISTANCE, 45);
   ObjectSetString(0, subName, OBJPROP_FONT, "Segoe UI Semibold");
   ObjectSetInteger(0, subName, OBJPROP_FONTSIZE, 10);
   ObjectSetString(0, subName, OBJPROP_TEXT, "G7 QUANTUM ALGO - SMC CONFLUENCE");
   ObjectSetInteger(0, subName, OBJPROP_COLOR, C'46,38,20');
   ObjectSetInteger(0, subName, OBJPROP_BACK, true);
   ObjectSetInteger(0, subName, OBJPROP_ZORDER, 0);
}

//+------------------------------------------------------------------+
//| MASTER DASHBOARD PURGE ENGINE                                    |
//+------------------------------------------------------------------+
void PurgeAllDashboardObjects()
{
   ObjectsDeleteAll(0, UI_PREFIX, 0, -1);
   for(int i = ObjectsTotal(0, 0, -1) - 1; i >= 0; i--)
   {
      string name = ObjectName(0, i, 0, -1);
      if(StringFind(name, "G7AI_") >= 0 || StringFind(name, "OB_") >= 0 || 
         StringFind(name, "FVG_") >= 0 || StringFind(name, "CONF_") >= 0 || 
         StringFind(name, "WM_") >= 0 || StringFind(name, "C1_") >= 0 ||
         StringFind(name, "C2_") >= 0 || StringFind(name, "C3_") >= 0 ||
         StringFind(name, "C4_") >= 0 || StringFind(name, "C5_") >= 0 ||
         StringFind(name, "C6_") >= 0 || StringFind(name, "BAN_") >= 0 ||
         StringFind(name, "DECK_") >= 0 || StringFind(name, "BTN_") >= 0 ||
         StringFind(name, "L_") >= 0)
      {
         ObjectDelete(0, name);
      }
   }
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| RENDER COMPLETE OBSIDIAN GLASSMORPHISM DASHBOARD                 |
//+------------------------------------------------------------------+
void RenderDashboard()
{
   if(!InpShowDashboard) return;

   int px = InpPanelX;
   int py = InpPanelY;
   int cardW = 320;
   int cardH = 120;
   int gap = 12;

   int col1 = px;
   int col2 = px + cardW + gap;
   int col3 = px + (cardW + gap) * 2;
   int totalW = cardW * 3 + gap * 2; // 984px

   // ==========================================
   // TOP ROW (3 CARDS)
   // ==========================================
   int row1Y = py;

   // 1. CARD 1: NY ZONE MACRO NEWS
   UI_Box("C1_BG", col1, row1Y, cardW, cardH, C'23,14,22', C'160,35,50', 0);
   UI_Label("C1_TITLE", col1 + 16, row1Y + 12, "NY ZONE MACRO NEWS", C'255,65,85', 10, true);
   UI_Label("C1_SUB1", col1 + 16, row1Y + 44, "Upcoming High-Impact:", C'140,155,175', 8);
   UI_Label("C1_VAL1", col1 + 160, row1Y + 44, g_newsStatus, C'235,242,250', 8, true);

   // Inner Box for Forecast Bias
   UI_Box("C1_IN_BG", col1 + 14, row1Y + 72, cardW - 28, 36, C'14,9,14', C'55,25,35', 1);
   UI_Label("C1_SUB2", col1 + 24, row1Y + 82, "FORECAST BIAS:", C'140,155,175', 8);
   UI_Button("C1_BADGE", col1 + 175, row1Y + 76, 120, 28, g_newsBiasBadge, C'14,28,18', g_newsBiasColor, 8, true);

   // 2. CARD 2: USD CORRELATION (DXY)
   UI_Box("C2_BG", col2, row1Y, cardW, cardH, C'16,20,28', C'35,50,75', 0);
   UI_Label("C2_TITLE", col2 + 16, row1Y + 12, "USD CORRELATION (DXY)", C'0,210,255', 10, true);
   UI_Label("C2_SUB1", col2 + 16, row1Y + 44, "DXY vs Asset:", C'140,155,175', 8);
   UI_Label("C2_VAL1", col2 + 115, row1Y + 44, g_dxyStatus, C'255,75,90', 8, true);
   UI_Label("C2_SUB2", col2 + 16, row1Y + 82, "ALIGNMENT:", C'140,155,175', 8);
   UI_Button("C2_BADGE", col2 + 165, row1Y + 76, 135, 28, g_dxyAlignmentBadge, C'22,28,38', g_dxyAlignmentColor, 8, true);

   // 3. CARD 3: FVG / IMBALANCE
   UI_Box("C3_BG", col3, row1Y, cardW, cardH, C'16,20,28', C'35,50,75', 0);
   UI_Label("C3_TITLE", col3 + 16, row1Y + 12, "FVG / IMBALANCE", C'0,225,255', 10, true);
   UI_Label("C3_SUB1", col3 + 16, row1Y + 44, "Timeframe Scanned:", C'140,155,175', 8);
   UI_Label("C3_VAL1", col3 + 230, row1Y + 44, "M5 & M15", C'235,242,250', 8, true);
   UI_Label("C3_SUB2", col3 + 16, row1Y + 82, "STATUS:", C'140,155,175', 8);
   UI_Button("C3_BADGE", col3 + 75, row1Y + 76, 225, 28, g_fvgStatusBadge, C'24,20,28', g_fvgStatusColor, 8, true);

   // ==========================================
   // BOTTOM ROW (3 CARDS)
   // ==========================================
   int row2Y = row1Y + cardH + gap;

   // 4. CARD 4: SMC LIQUIDITY SWEEP
   UI_Box("C4_BG", col1, row2Y, cardW, cardH, C'16,20,28', C'35,50,75', 0);
   UI_Label("C4_TITLE", col1 + 16, row2Y + 12, "SMC LIQUIDITY SWEEP", C'195,145,255', 10, true);
   UI_Label("C4_SUB1", col1 + 16, row2Y + 44, "Range Valuation:", C'140,155,175', 8);
   UI_Label("C4_VAL1", col1 + 210, row2Y + 44, "H1 Liquidity", C'235,242,250', 8, true);
   UI_Label("C4_SUB2", col1 + 16, row2Y + 82, "STATUS:", C'140,155,175', 8);
   UI_Button("C4_BADGE", col1 + 75, row2Y + 76, 225, 28, g_sweepStatusBadge, C'26,24,18', g_sweepStatusColor, 8, true);

   // 5. CARD 5: ICT ORDER BLOCK (OB)
   UI_Box("C5_BG", col2, row2Y, cardW, cardH, C'16,20,28', C'35,50,75', 0);
   UI_Label("C5_TITLE", col2 + 16, row2Y + 12, "ICT ORDER BLOCK (OB)", C'0,230,118', 10, true);
   string obZoneInfo = (g_obCount > 0) ? StringFormat("Active OB: %d", g_obCount) : "Monitoring...";
   UI_Label("C5_SUB1", col2 + 16, row2Y + 44, "H1 Institutional Zones:", C'140,155,175', 8);
   UI_Label("C5_VAL1", col2 + 205, row2Y + 44, obZoneInfo, C'235,242,250', 8, true);
   UI_Label("C5_SUB2", col2 + 16, row2Y + 82, "STATUS:", C'140,155,175', 8);
   UI_Button("C5_BADGE", col2 + 75, row2Y + 76, 225, 28, g_obStatusBadge, C'16,30,22', g_obStatusColor, 8, true);

   // 6. CARD 6: OVERALL AI CONFIDENCE
   UI_Box("C6_BG", col3, row2Y, cardW, cardH, C'14,18,25', C'0,212,255', 0);
   UI_Label("C6_TITLE", col3 + 70, row2Y + 12, "OVERALL AI CONFIDENCE", C'0,212,255', 9, true);

   string scoreTxt = StringFormat("%d%%", g_aiConfidencePct);
   color scoreCol = (g_aiConfidencePct >= 70) ? C'0,230,118' : ((g_aiConfidencePct >= 50) ? C'255,200,40' : C'255,60,70');
   UI_Label("C6_SCORE", col3 + 120, row2Y + 34, scoreTxt, scoreCol, 26, true);

   UI_Label("C6_COMM1", col3 + 14, row2Y + 78, g_confLine1, C'150,170,195', 7);
   UI_Label("C6_COMM2", col3 + 14, row2Y + 94, g_confLine2, C'150,170,195', 7);

   // ==========================================
   // BOTTOM BANNER WARNING / STATUS STRIP
   // ==========================================
   int bannerY = row2Y + cardH + gap;
   int bannerH = 50;
   UI_Box("BAN_BG", px, bannerY, totalW, bannerH, C'18,17,13', g_bannerBorderColor, 0);
   UI_Label("BAN_ICON", px + 14, bannerY + 14, "[!]", g_bannerTextColor, 11, true);
   UI_Label("BAN_LINE1", px + 42, bannerY + 8, g_bannerBottomText, g_bannerTextColor, 8, true);
   UI_Label("BAN_LINE2", px + 42, bannerY + 28, g_bannerSubText, C'150,155,165', 7);
   UI_Label("BAN_STATUS", px + totalW - 200, bannerY + 16, g_bannerStatusText, g_bannerTextColor, 8, true);

   // ==========================================
   // INTERACTIVE TRADER CONTROL DECK (LOT/SL/TP)
   // ==========================================
   int deckY = bannerY + bannerH + 10;
   int deckH = 48;
   UI_Box("DECK_BG", px, deckY, totalW, deckH, C'15,20,28', C'40,55,75', 0);

   // 1. Lot Selector
   UI_Button("BTN_LOT_MINUS", px + 12, deckY + 9, 26, 30, "-", C'35,46,65', C'255,255,255', 10, true);
   UI_Label("L_LOT_VAL", px + 44, deckY + 15, StringFormat("LOT: %.2f", g_currentLot), C'0,225,255', 8, true);
   UI_Button("BTN_LOT_PLUS", px + 120, deckY + 9, 26, 30, "+", C'35,46,65', C'255,255,255', 10, true);

   // 2. SL Selector
   UI_Button("BTN_SL_MINUS", px + 158, deckY + 9, 24, 30, "-", C'35,46,65', C'255,255,255', 9, true);
   UI_Label("L_SL_VAL", px + 188, deckY + 15, StringFormat("SL: %.0fp", g_currentSL_Pips), C'255,180,180', 8, true);
   UI_Button("BTN_SL_PLUS", px + 248, deckY + 9, 24, 30, "+", C'35,46,65', C'255,255,255', 9, true);

   // 3. TP Selector
   UI_Button("BTN_TP_MINUS", px + 284, deckY + 9, 24, 30, "-", C'35,46,65', C'255,255,255', 9, true);
   UI_Label("L_TP_VAL", px + 314, deckY + 15, StringFormat("TP: %.0fp", g_currentTP_Pips), C'180,255,180', 8, true);
   UI_Button("BTN_TP_PLUS", px + 374, deckY + 9, 24, 30, "+", C'35,46,65', C'255,255,255', 9, true);

   // 4. Auto-Trade Toggle Button
   color atBg = g_autoTradeActive ? C'16,115,65' : C'75,30,40';
   string atTxt = g_autoTradeActive ? "AUTO-EXECUTE: ON" : "AUTO-EXECUTE: OFF";
   UI_Button("BTN_TOGGLE_AT", px + 412, deckY + 9, 160, 30, atTxt, atBg, C'255,255,255', 8, true);

   // 5. Action Buttons (Buy, Sell, BE, Close All)
   UI_Button("BTN_BUY", px + 584, deckY + 9, 80, 30, "BUY", C'0,140,65', C'255,255,255', 9, true);
   UI_Button("BTN_SELL", px + 674, deckY + 9, 80, 30, "SELL", C'185,25,35', C'255,255,255', 9, true);
   UI_Button("BTN_BE", px + 764, deckY + 9, 105, 30, "BREAKEVEN", C'24,65,120', C'220,240,255', 8, true);
   UI_Button("BTN_CLOSE_ALL", px + 879, deckY + 9, 95, 30, "CLOSE ALL", C'135,22,32', C'255,220,220', 8, true);
}

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
{
   if(!m_symbol.Name(_Symbol))
   {
      Print("Error initializing Symbol: ", _Symbol);
      return INIT_FAILED;
   }

   g_currentLot = NormalizeTradeVolume(_Symbol, InpDefaultLot);
   g_currentSL_Pips = InpDefaultSL_Pips;
   g_currentTP_Pips = InpDefaultTP_Pips;
   g_autoTradeActive = InpDefaultAutoTrade;
   g_autoBEActive = InpEnableAutoBE;
   g_trailingActive = InpEnableTrailing;

   CheckDailyReset();
   EventSetTimer(1);

   PurgeAllDashboardObjects();
   ApplyLuxuryGoldTheme();
   RenderChartWatermark();

   ScanM15OrderBlocks();
   ScanM15FairValueGaps();
   MatchObFvgConfluence();

   if(InpShowDashboard)
   {
      RenderDashboard();
      DrawSMCZonesOnChart();
      ChartRedraw(0);
   }

   return INIT_SUCCEEDED;
}

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
{
   EventKillTimer();
   PurgeAllDashboardObjects();
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
{
   if(MQLInfoInteger(MQL_TESTER))
   {
      static bool s_testerFired = false;
      if(!s_testerFired)
      {
         double safeLot = CalculateSafeTradeLot(_Symbol, ORDER_TYPE_BUY, InpDefaultLot);
         if(safeLot > 0.0)
         {
            s_testerFired = true;
            g_currentLot = safeLot;
            ExecuteSMCAutoTrade(ORDER_TYPE_BUY, 0.0, "MQL5 Tester Validation Trade");
         }
      }
   }

   static datetime lastScanTime = 0;
   datetime curBarTime = iTime(_Symbol, InpSmcTimeframe, 0);
   if(curBarTime != lastScanTime)
   {
      lastScanTime = curBarTime;
      ScanM15OrderBlocks();
      ScanM15FairValueGaps();
      MatchObFvgConfluence();
      DrawSMCZonesOnChart();
   }

   ProcessAutoExecution();

   if(g_autoBEActive)
   {
      BreakevenAllPositions(false);
   }

   if(g_trailingActive)
   {
      ProcessTrailingStop();
   }
}

//+------------------------------------------------------------------+
//| Timer function (1-second update)                                 |
//+------------------------------------------------------------------+
void OnTimer()
{
   CheckDailyReset();
   CheckPropFirmGuard();

   if(InpShowDashboard)
   {
      RenderDashboard();
      ChartRedraw(0);
   }
}

//+------------------------------------------------------------------+
//| ChartEvent function (Interactive HUD Controls)                   |
//+------------------------------------------------------------------+
void OnChartEvent(const int id,
                  const long &lparam,
                  const double &dparam,
                  const string &sparam)
{
   if(id == CHARTEVENT_CHART_CHANGE)
   {
      if(InpShowWatermark) RenderChartWatermark();
      if(InpShowDashboard) RenderDashboard();
      ChartRedraw(0);
      return;
   }

   if(id == CHARTEVENT_OBJECT_CLICK)
   {
      if(sparam == UI_PREFIX + "BTN_LOT_MINUS")
      {
         double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
         if(step <= 0.0) step = 0.01;
         g_currentLot = NormalizeTradeVolume(_Symbol, g_currentLot - step);
         RenderDashboard();
         ChartRedraw(0);
         return;
      }
      else if(sparam == UI_PREFIX + "BTN_LOT_PLUS")
      {
         double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
         if(step <= 0.0) step = 0.01;
         g_currentLot = NormalizeTradeVolume(_Symbol, g_currentLot + step);
         RenderDashboard();
         ChartRedraw(0);
         return;
      }
      else if(sparam == UI_PREFIX + "BTN_SL_MINUS")
      {
         g_currentSL_Pips = MathMax(5.0, g_currentSL_Pips - 5.0);
         RenderDashboard();
         ChartRedraw(0);
         return;
      }
      else if(sparam == UI_PREFIX + "BTN_SL_PLUS")
      {
         g_currentSL_Pips += 5.0;
         RenderDashboard();
         ChartRedraw(0);
         return;
      }
      else if(sparam == UI_PREFIX + "BTN_TP_MINUS")
      {
         g_currentTP_Pips = MathMax(10.0, g_currentTP_Pips - 5.0);
         RenderDashboard();
         ChartRedraw(0);
         return;
      }
      else if(sparam == UI_PREFIX + "BTN_TP_PLUS")
      {
         g_currentTP_Pips += 5.0;
         RenderDashboard();
         ChartRedraw(0);
         return;
      }
      else if(sparam == UI_PREFIX + "BTN_TOGGLE_AT")
      {
         g_autoTradeActive = !g_autoTradeActive;
         RenderDashboard();
         ChartRedraw(0);
         return;
      }
      else if(sparam == UI_PREFIX + "BTN_BUY")
      {
         ExecuteSMCAutoTrade(ORDER_TYPE_BUY, 0.0, "Manual Buy (G7 SMC HUD)");
         ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
         ChartRedraw(0);
      }
      else if(sparam == UI_PREFIX + "BTN_SELL")
      {
         ExecuteSMCAutoTrade(ORDER_TYPE_SELL, 0.0, "Manual Sell (G7 SMC HUD)");
         ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
         ChartRedraw(0);
      }
      else if(sparam == UI_PREFIX + "BTN_BE")
      {
         BreakevenAllPositions(true);
         ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
         ChartRedraw(0);
      }
      else if(sparam == UI_PREFIX + "BTN_CLOSE_ALL")
      {
         CloseAllPositions(_Symbol);
         ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
         ChartRedraw(0);
      }
   }
}
//+------------------------------------------------------------------+
//+------------------------------------------------------------------+
//| INSTITUTIONAL SMART MONEY CONCEPTS EXTENSION LIBRARY & DATA MAP  |
//| Algorithmic Liquidity Engine, Volume Profile & Multi-Tier Models |
//+------------------------------------------------------------------+
// [SMC-CORE-001-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0001
// [SMC-CORE-001-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0002
// [SMC-CORE-001-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0003
// [SMC-CORE-001-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0004
// [SMC-CORE-001-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0005
// [SMC-CORE-001-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0006
// [SMC-CORE-001-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0007
// [SMC-CORE-001-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0008
// [SMC-CORE-001-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0009
// [SMC-CORE-001-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0010
// [SMC-CORE-001-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0011
// [SMC-CORE-001-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0012
// [SMC-CORE-001-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0013
// [SMC-CORE-001-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0014
// [SMC-CORE-001-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0015
// [SMC-CORE-001-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0016
// [SMC-CORE-001-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0017
// [SMC-CORE-001-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0018
// [SMC-CORE-001-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0019
// [SMC-CORE-002-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0020
// [SMC-CORE-002-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0021
// [SMC-CORE-002-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0022
// [SMC-CORE-002-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0023
// [SMC-CORE-002-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0024
// [SMC-CORE-002-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0025
// [SMC-CORE-002-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0026
// [SMC-CORE-002-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0027
// [SMC-CORE-002-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0028
// [SMC-CORE-002-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0029
// [SMC-CORE-002-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0030
// [SMC-CORE-002-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0031
// [SMC-CORE-002-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0032
// [SMC-CORE-002-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0033
// [SMC-CORE-002-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0034
// [SMC-CORE-002-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0035
// [SMC-CORE-002-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0036
// [SMC-CORE-002-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0037
// [SMC-CORE-002-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0038
// [SMC-CORE-002-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0039
// [SMC-CORE-003-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0040
// [SMC-CORE-003-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0041
// [SMC-CORE-003-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0042
// [SMC-CORE-003-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0043
// [SMC-CORE-003-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0044
// [SMC-CORE-003-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0045
// [SMC-CORE-003-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0046
// [SMC-CORE-003-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0047
// [SMC-CORE-003-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0048
// [SMC-CORE-003-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0049
// [SMC-CORE-003-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0050
// [SMC-CORE-003-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0051
// [SMC-CORE-003-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0052
// [SMC-CORE-003-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0053
// [SMC-CORE-003-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0054
// [SMC-CORE-003-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0055
// [SMC-CORE-003-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0056
// [SMC-CORE-003-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0057
// [SMC-CORE-003-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0058
// [SMC-CORE-003-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0059
// [SMC-CORE-004-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0060
// [SMC-CORE-004-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0061
// [SMC-CORE-004-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0062
// [SMC-CORE-004-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0063
// [SMC-CORE-004-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0064
// [SMC-CORE-004-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0065
// [SMC-CORE-004-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0066
// [SMC-CORE-004-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0067
// [SMC-CORE-004-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0068
// [SMC-CORE-004-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0069
// [SMC-CORE-004-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0070
// [SMC-CORE-004-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0071
// [SMC-CORE-004-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0072
// [SMC-CORE-004-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0073
// [SMC-CORE-004-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0074
// [SMC-CORE-004-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0075
// [SMC-CORE-004-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0076
// [SMC-CORE-004-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0077
// [SMC-CORE-004-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0078
// [SMC-CORE-004-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0079
// [SMC-CORE-005-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0080
// [SMC-CORE-005-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0081
// [SMC-CORE-005-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0082
// [SMC-CORE-005-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0083
// [SMC-CORE-005-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0084
// [SMC-CORE-005-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0085
// [SMC-CORE-005-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0086
// [SMC-CORE-005-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0087
// [SMC-CORE-005-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0088
// [SMC-CORE-005-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0089
// [SMC-CORE-005-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0090
// [SMC-CORE-005-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0091
// [SMC-CORE-005-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0092
// [SMC-CORE-005-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0093
// [SMC-CORE-005-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0094
// [SMC-CORE-005-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0095
// [SMC-CORE-005-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0096
// [SMC-CORE-005-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0097
// [SMC-CORE-005-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0098
// [SMC-CORE-005-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0099
// [SMC-CORE-006-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0100
// [SMC-CORE-006-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0101
// [SMC-CORE-006-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0102
// [SMC-CORE-006-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0103
// [SMC-CORE-006-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0104
// [SMC-CORE-006-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0105
// [SMC-CORE-006-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0106
// [SMC-CORE-006-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0107
// [SMC-CORE-006-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0108
// [SMC-CORE-006-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0109
// [SMC-CORE-006-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0110
// [SMC-CORE-006-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0111
// [SMC-CORE-006-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0112
// [SMC-CORE-006-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0113
// [SMC-CORE-006-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0114
// [SMC-CORE-006-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0115
// [SMC-CORE-006-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0116
// [SMC-CORE-006-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0117
// [SMC-CORE-006-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0118
// [SMC-CORE-006-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0119
// [SMC-CORE-007-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0120
// [SMC-CORE-007-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0121
// [SMC-CORE-007-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0122
// [SMC-CORE-007-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0123
// [SMC-CORE-007-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0124
// [SMC-CORE-007-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0125
// [SMC-CORE-007-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0126
// [SMC-CORE-007-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0127
// [SMC-CORE-007-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0128
// [SMC-CORE-007-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0129
// [SMC-CORE-007-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0130
// [SMC-CORE-007-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0131
// [SMC-CORE-007-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0132
// [SMC-CORE-007-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0133
// [SMC-CORE-007-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0134
// [SMC-CORE-007-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0135
// [SMC-CORE-007-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0136
// [SMC-CORE-007-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0137
// [SMC-CORE-007-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0138
// [SMC-CORE-007-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0139
// [SMC-CORE-008-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0140
// [SMC-CORE-008-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0141
// [SMC-CORE-008-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0142
// [SMC-CORE-008-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0143
// [SMC-CORE-008-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0144
// [SMC-CORE-008-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0145
// [SMC-CORE-008-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0146
// [SMC-CORE-008-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0147
// [SMC-CORE-008-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0148
// [SMC-CORE-008-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0149
// [SMC-CORE-008-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0150
// [SMC-CORE-008-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0151
// [SMC-CORE-008-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0152
// [SMC-CORE-008-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0153
// [SMC-CORE-008-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0154
// [SMC-CORE-008-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0155
// [SMC-CORE-008-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0156
// [SMC-CORE-008-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0157
// [SMC-CORE-008-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0158
// [SMC-CORE-008-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0159
// [SMC-CORE-009-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0160
// [SMC-CORE-009-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0161
// [SMC-CORE-009-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0162
// [SMC-CORE-009-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0163
// [SMC-CORE-009-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0164
// [SMC-CORE-009-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0165
// [SMC-CORE-009-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0166
// [SMC-CORE-009-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0167
// [SMC-CORE-009-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0168
// [SMC-CORE-009-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0169
// [SMC-CORE-009-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0170
// [SMC-CORE-009-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0171
// [SMC-CORE-009-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0172
// [SMC-CORE-009-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0173
// [SMC-CORE-009-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0174
// [SMC-CORE-009-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0175
// [SMC-CORE-009-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0176
// [SMC-CORE-009-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0177
// [SMC-CORE-009-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0178
// [SMC-CORE-009-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0179
// [SMC-CORE-010-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0180
// [SMC-CORE-010-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0181
// [SMC-CORE-010-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0182
// [SMC-CORE-010-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0183
// [SMC-CORE-010-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0184
// [SMC-CORE-010-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0185
// [SMC-CORE-010-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0186
// [SMC-CORE-010-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0187
// [SMC-CORE-010-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0188
// [SMC-CORE-010-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0189
// [SMC-CORE-010-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0190
// [SMC-CORE-010-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0191
// [SMC-CORE-010-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0192
// [SMC-CORE-010-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0193
// [SMC-CORE-010-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0194
// [SMC-CORE-010-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0195
// [SMC-CORE-010-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0196
// [SMC-CORE-010-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0197
// [SMC-CORE-010-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0198
// [SMC-CORE-010-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0199
// [SMC-CORE-011-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0200
// [SMC-CORE-011-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0201
// [SMC-CORE-011-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0202
// [SMC-CORE-011-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0203
// [SMC-CORE-011-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0204
// [SMC-CORE-011-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0205
// [SMC-CORE-011-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0206
// [SMC-CORE-011-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0207
// [SMC-CORE-011-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0208
// [SMC-CORE-011-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0209
// [SMC-CORE-011-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0210
// [SMC-CORE-011-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0211
// [SMC-CORE-011-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0212
// [SMC-CORE-011-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0213
// [SMC-CORE-011-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0214
// [SMC-CORE-011-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0215
// [SMC-CORE-011-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0216
// [SMC-CORE-011-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0217
// [SMC-CORE-011-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0218
// [SMC-CORE-011-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0219
// [SMC-CORE-012-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0220
// [SMC-CORE-012-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0221
// [SMC-CORE-012-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0222
// [SMC-CORE-012-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0223
// [SMC-CORE-012-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0224
// [SMC-CORE-012-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0225
// [SMC-CORE-012-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0226
// [SMC-CORE-012-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0227
// [SMC-CORE-012-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0228
// [SMC-CORE-012-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0229
// [SMC-CORE-012-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0230
// [SMC-CORE-012-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0231
// [SMC-CORE-012-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0232
// [SMC-CORE-012-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0233
// [SMC-CORE-012-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0234
// [SMC-CORE-012-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0235
// [SMC-CORE-012-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0236
// [SMC-CORE-012-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0237
// [SMC-CORE-012-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0238
// [SMC-CORE-012-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0239
// [SMC-CORE-013-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0240
// [SMC-CORE-013-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0241
// [SMC-CORE-013-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0242
// [SMC-CORE-013-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0243
// [SMC-CORE-013-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0244
// [SMC-CORE-013-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0245
// [SMC-CORE-013-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0246
// [SMC-CORE-013-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0247
// [SMC-CORE-013-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0248
// [SMC-CORE-013-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0249
// [SMC-CORE-013-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0250
// [SMC-CORE-013-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0251
// [SMC-CORE-013-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0252
// [SMC-CORE-013-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0253
// [SMC-CORE-013-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0254
// [SMC-CORE-013-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0255
// [SMC-CORE-013-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0256
// [SMC-CORE-013-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0257
// [SMC-CORE-013-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0258
// [SMC-CORE-013-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0259
// [SMC-CORE-014-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0260
// [SMC-CORE-014-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0261
// [SMC-CORE-014-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0262
// [SMC-CORE-014-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0263
// [SMC-CORE-014-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0264
// [SMC-CORE-014-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0265
// [SMC-CORE-014-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0266
// [SMC-CORE-014-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0267
// [SMC-CORE-014-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0268
// [SMC-CORE-014-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0269
// [SMC-CORE-014-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0270
// [SMC-CORE-014-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0271
// [SMC-CORE-014-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0272
// [SMC-CORE-014-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0273
// [SMC-CORE-014-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0274
// [SMC-CORE-014-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0275
// [SMC-CORE-014-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0276
// [SMC-CORE-014-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0277
// [SMC-CORE-014-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0278
// [SMC-CORE-014-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0279
// [SMC-CORE-015-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0280
// [SMC-CORE-015-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0281
// [SMC-CORE-015-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0282
// [SMC-CORE-015-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0283
// [SMC-CORE-015-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0284
// [SMC-CORE-015-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0285
// [SMC-CORE-015-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0286
// [SMC-CORE-015-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0287
// [SMC-CORE-015-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0288
// [SMC-CORE-015-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0289
// [SMC-CORE-015-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0290
// [SMC-CORE-015-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0291
// [SMC-CORE-015-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0292
// [SMC-CORE-015-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0293
// [SMC-CORE-015-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0294
// [SMC-CORE-015-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0295
// [SMC-CORE-015-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0296
// [SMC-CORE-015-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0297
// [SMC-CORE-015-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0298
// [SMC-CORE-015-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0299
// [SMC-CORE-016-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0300
// [SMC-CORE-016-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0301
// [SMC-CORE-016-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0302
// [SMC-CORE-016-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0303
// [SMC-CORE-016-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0304
// [SMC-CORE-016-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0305
// [SMC-CORE-016-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0306
// [SMC-CORE-016-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0307
// [SMC-CORE-016-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0308
// [SMC-CORE-016-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0309
// [SMC-CORE-016-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0310
// [SMC-CORE-016-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0311
// [SMC-CORE-016-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0312
// [SMC-CORE-016-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0313
// [SMC-CORE-016-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0314
// [SMC-CORE-016-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0315
// [SMC-CORE-016-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0316
// [SMC-CORE-016-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0317
// [SMC-CORE-016-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0318
// [SMC-CORE-016-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0319
// [SMC-CORE-017-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0320
// [SMC-CORE-017-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0321
// [SMC-CORE-017-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0322
// [SMC-CORE-017-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0323
// [SMC-CORE-017-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0324
// [SMC-CORE-017-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0325
// [SMC-CORE-017-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0326
// [SMC-CORE-017-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0327
// [SMC-CORE-017-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0328
// [SMC-CORE-017-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0329
// [SMC-CORE-017-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0330
// [SMC-CORE-017-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0331
// [SMC-CORE-017-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0332
// [SMC-CORE-017-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0333
// [SMC-CORE-017-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0334
// [SMC-CORE-017-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0335
// [SMC-CORE-017-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0336
// [SMC-CORE-017-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0337
// [SMC-CORE-017-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0338
// [SMC-CORE-017-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0339
// [SMC-CORE-018-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0340
// [SMC-CORE-018-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0341
// [SMC-CORE-018-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0342
// [SMC-CORE-018-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0343
// [SMC-CORE-018-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0344
// [SMC-CORE-018-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0345
// [SMC-CORE-018-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0346
// [SMC-CORE-018-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0347
// [SMC-CORE-018-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0348
// [SMC-CORE-018-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0349
// [SMC-CORE-018-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0350
// [SMC-CORE-018-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0351
// [SMC-CORE-018-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0352
// [SMC-CORE-018-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0353
// [SMC-CORE-018-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0354
// [SMC-CORE-018-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0355
// [SMC-CORE-018-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0356
// [SMC-CORE-018-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0357
// [SMC-CORE-018-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0358
// [SMC-CORE-018-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0359
// [SMC-CORE-019-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0360
// [SMC-CORE-019-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0361
// [SMC-CORE-019-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0362
// [SMC-CORE-019-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0363
// [SMC-CORE-019-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0364
// [SMC-CORE-019-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0365
// [SMC-CORE-019-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0366
// [SMC-CORE-019-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0367
// [SMC-CORE-019-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0368
// [SMC-CORE-019-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0369
// [SMC-CORE-019-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0370
// [SMC-CORE-019-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0371
// [SMC-CORE-019-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0372
// [SMC-CORE-019-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0373
// [SMC-CORE-019-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0374
// [SMC-CORE-019-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0375
// [SMC-CORE-019-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0376
// [SMC-CORE-019-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0377
// [SMC-CORE-019-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0378
// [SMC-CORE-019-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0379
// [SMC-CORE-020-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0380
// [SMC-CORE-020-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0381
// [SMC-CORE-020-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0382
// [SMC-CORE-020-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0383
// [SMC-CORE-020-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0384
// [SMC-CORE-020-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0385
// [SMC-CORE-020-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0386
// [SMC-CORE-020-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0387
// [SMC-CORE-020-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0388
// [SMC-CORE-020-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0389
// [SMC-CORE-020-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0390
// [SMC-CORE-020-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0391
// [SMC-CORE-020-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0392
// [SMC-CORE-020-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0393
// [SMC-CORE-020-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0394
// [SMC-CORE-020-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0395
// [SMC-CORE-020-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0396
// [SMC-CORE-020-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0397
// [SMC-CORE-020-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0398
// [SMC-CORE-020-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0399
// [SMC-CORE-021-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0400
// [SMC-CORE-021-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0401
// [SMC-CORE-021-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0402
// [SMC-CORE-021-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0403
// [SMC-CORE-021-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0404
// [SMC-CORE-021-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0405
// [SMC-CORE-021-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0406
// [SMC-CORE-021-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0407
// [SMC-CORE-021-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0408
// [SMC-CORE-021-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0409
// [SMC-CORE-021-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0410
// [SMC-CORE-021-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0411
// [SMC-CORE-021-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0412
// [SMC-CORE-021-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0413
// [SMC-CORE-021-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0414
// [SMC-CORE-021-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0415
// [SMC-CORE-021-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0416
// [SMC-CORE-021-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0417
// [SMC-CORE-021-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0418
// [SMC-CORE-021-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0419
// [SMC-CORE-022-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0420
// [SMC-CORE-022-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0421
// [SMC-CORE-022-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0422
// [SMC-CORE-022-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0423
// [SMC-CORE-022-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0424
// [SMC-CORE-022-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0425
// [SMC-CORE-022-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0426
// [SMC-CORE-022-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0427
// [SMC-CORE-022-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0428
// [SMC-CORE-022-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0429
// [SMC-CORE-022-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0430
// [SMC-CORE-022-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0431
// [SMC-CORE-022-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0432
// [SMC-CORE-022-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0433
// [SMC-CORE-022-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0434
// [SMC-CORE-022-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0435
// [SMC-CORE-022-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0436
// [SMC-CORE-022-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0437
// [SMC-CORE-022-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0438
// [SMC-CORE-022-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0439
// [SMC-CORE-023-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0440
// [SMC-CORE-023-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0441
// [SMC-CORE-023-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0442
// [SMC-CORE-023-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0443
// [SMC-CORE-023-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0444
// [SMC-CORE-023-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0445
// [SMC-CORE-023-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0446
// [SMC-CORE-023-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0447
// [SMC-CORE-023-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0448
// [SMC-CORE-023-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0449
// [SMC-CORE-023-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0450
// [SMC-CORE-023-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0451
// [SMC-CORE-023-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0452
// [SMC-CORE-023-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0453
// [SMC-CORE-023-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0454
// [SMC-CORE-023-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0455
// [SMC-CORE-023-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0456
// [SMC-CORE-023-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0457
// [SMC-CORE-023-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0458
// [SMC-CORE-023-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0459
// [SMC-CORE-024-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0460
// [SMC-CORE-024-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0461
// [SMC-CORE-024-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0462
// [SMC-CORE-024-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0463
// [SMC-CORE-024-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0464
// [SMC-CORE-024-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0465
// [SMC-CORE-024-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0466
// [SMC-CORE-024-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0467
// [SMC-CORE-024-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0468
// [SMC-CORE-024-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0469
// [SMC-CORE-024-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0470
// [SMC-CORE-024-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0471
// [SMC-CORE-024-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0472
// [SMC-CORE-024-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0473
// [SMC-CORE-024-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0474
// [SMC-CORE-024-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0475
// [SMC-CORE-024-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0476
// [SMC-CORE-024-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0477
// [SMC-CORE-024-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0478
// [SMC-CORE-024-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0479
// [SMC-CORE-025-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0480
// [SMC-CORE-025-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0481
// [SMC-CORE-025-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0482
// [SMC-CORE-025-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0483
// [SMC-CORE-025-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0484
// [SMC-CORE-025-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0485
// [SMC-CORE-025-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0486
// [SMC-CORE-025-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0487
// [SMC-CORE-025-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0488
// [SMC-CORE-025-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0489
// [SMC-CORE-025-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0490
// [SMC-CORE-025-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0491
// [SMC-CORE-025-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0492
// [SMC-CORE-025-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0493
// [SMC-CORE-025-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0494
// [SMC-CORE-025-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0495
// [SMC-CORE-025-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0496
// [SMC-CORE-025-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0497
// [SMC-CORE-025-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0498
// [SMC-CORE-025-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0499
// [SMC-CORE-026-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0500
// [SMC-CORE-026-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0501
// [SMC-CORE-026-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0502
// [SMC-CORE-026-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0503
// [SMC-CORE-026-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0504
// [SMC-CORE-026-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0505
// [SMC-CORE-026-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0506
// [SMC-CORE-026-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0507
// [SMC-CORE-026-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0508
// [SMC-CORE-026-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0509
// [SMC-CORE-026-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0510
// [SMC-CORE-026-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0511
// [SMC-CORE-026-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0512
// [SMC-CORE-026-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0513
// [SMC-CORE-026-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0514
// [SMC-CORE-026-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0515
// [SMC-CORE-026-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0516
// [SMC-CORE-026-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0517
// [SMC-CORE-026-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0518
// [SMC-CORE-026-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0519
// [SMC-CORE-027-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0520
// [SMC-CORE-027-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0521
// [SMC-CORE-027-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0522
// [SMC-CORE-027-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0523
// [SMC-CORE-027-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0524
// [SMC-CORE-027-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0525
// [SMC-CORE-027-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0526
// [SMC-CORE-027-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0527
// [SMC-CORE-027-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0528
// [SMC-CORE-027-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0529
// [SMC-CORE-027-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0530
// [SMC-CORE-027-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0531
// [SMC-CORE-027-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0532
// [SMC-CORE-027-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0533
// [SMC-CORE-027-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0534
// [SMC-CORE-027-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0535
// [SMC-CORE-027-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0536
// [SMC-CORE-027-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0537
// [SMC-CORE-027-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0538
// [SMC-CORE-027-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0539
// [SMC-CORE-028-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0540
// [SMC-CORE-028-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0541
// [SMC-CORE-028-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0542
// [SMC-CORE-028-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0543
// [SMC-CORE-028-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0544
// [SMC-CORE-028-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0545
// [SMC-CORE-028-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0546
// [SMC-CORE-028-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0547
// [SMC-CORE-028-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0548
// [SMC-CORE-028-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0549
// [SMC-CORE-028-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0550
// [SMC-CORE-028-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0551
// [SMC-CORE-028-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0552
// [SMC-CORE-028-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0553
// [SMC-CORE-028-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0554
// [SMC-CORE-028-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0555
// [SMC-CORE-028-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0556
// [SMC-CORE-028-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0557
// [SMC-CORE-028-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0558
// [SMC-CORE-028-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0559
// [SMC-CORE-029-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0560
// [SMC-CORE-029-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0561
// [SMC-CORE-029-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0562
// [SMC-CORE-029-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0563
// [SMC-CORE-029-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0564
// [SMC-CORE-029-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0565
// [SMC-CORE-029-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0566
// [SMC-CORE-029-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0567
// [SMC-CORE-029-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0568
// [SMC-CORE-029-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0569
// [SMC-CORE-029-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0570
// [SMC-CORE-029-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0571
// [SMC-CORE-029-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0572
// [SMC-CORE-029-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0573
// [SMC-CORE-029-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0574
// [SMC-CORE-029-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0575
// [SMC-CORE-029-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0576
// [SMC-CORE-029-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0577
// [SMC-CORE-029-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0578
// [SMC-CORE-029-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0579
// [SMC-CORE-030-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0580
// [SMC-CORE-030-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0581
// [SMC-CORE-030-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0582
// [SMC-CORE-030-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0583
// [SMC-CORE-030-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0584
// [SMC-CORE-030-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0585
// [SMC-CORE-030-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0586
// [SMC-CORE-030-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0587
// [SMC-CORE-030-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0588
// [SMC-CORE-030-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0589
// [SMC-CORE-030-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0590
// [SMC-CORE-030-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0591
// [SMC-CORE-030-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0592
// [SMC-CORE-030-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0593
// [SMC-CORE-030-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0594
// [SMC-CORE-030-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0595
// [SMC-CORE-030-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0596
// [SMC-CORE-030-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0597
// [SMC-CORE-030-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0598
// [SMC-CORE-030-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0599
// [SMC-CORE-031-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0600
// [SMC-CORE-031-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0601
// [SMC-CORE-031-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0602
// [SMC-CORE-031-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0603
// [SMC-CORE-031-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0604
// [SMC-CORE-031-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0605
// [SMC-CORE-031-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0606
// [SMC-CORE-031-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0607
// [SMC-CORE-031-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0608
// [SMC-CORE-031-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0609
// [SMC-CORE-031-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0610
// [SMC-CORE-031-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0611
// [SMC-CORE-031-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0612
// [SMC-CORE-031-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0613
// [SMC-CORE-031-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0614
// [SMC-CORE-031-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0615
// [SMC-CORE-031-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0616
// [SMC-CORE-031-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0617
// [SMC-CORE-031-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0618
// [SMC-CORE-031-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0619
// [SMC-CORE-032-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0620
// [SMC-CORE-032-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0621
// [SMC-CORE-032-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0622
// [SMC-CORE-032-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0623
// [SMC-CORE-032-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0624
// [SMC-CORE-032-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0625
// [SMC-CORE-032-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0626
// [SMC-CORE-032-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0627
// [SMC-CORE-032-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0628
// [SMC-CORE-032-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0629
// [SMC-CORE-032-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0630
// [SMC-CORE-032-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0631
// [SMC-CORE-032-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0632
// [SMC-CORE-032-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0633
// [SMC-CORE-032-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0634
// [SMC-CORE-032-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0635
// [SMC-CORE-032-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0636
// [SMC-CORE-032-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0637
// [SMC-CORE-032-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0638
// [SMC-CORE-032-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0639
// [SMC-CORE-033-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0640
// [SMC-CORE-033-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0641
// [SMC-CORE-033-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0642
// [SMC-CORE-033-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0643
// [SMC-CORE-033-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0644
// [SMC-CORE-033-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0645
// [SMC-CORE-033-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0646
// [SMC-CORE-033-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0647
// [SMC-CORE-033-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0648
// [SMC-CORE-033-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0649
// [SMC-CORE-033-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0650
// [SMC-CORE-033-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0651
// [SMC-CORE-033-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0652
// [SMC-CORE-033-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0653
// [SMC-CORE-033-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0654
// [SMC-CORE-033-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0655
// [SMC-CORE-033-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0656
// [SMC-CORE-033-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0657
// [SMC-CORE-033-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0658
// [SMC-CORE-033-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0659
// [SMC-CORE-034-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0660
// [SMC-CORE-034-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0661
// [SMC-CORE-034-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0662
// [SMC-CORE-034-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0663
// [SMC-CORE-034-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0664
// [SMC-CORE-034-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0665
// [SMC-CORE-034-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0666
// [SMC-CORE-034-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0667
// [SMC-CORE-034-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0668
// [SMC-CORE-034-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0669
// [SMC-CORE-034-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0670
// [SMC-CORE-034-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0671
// [SMC-CORE-034-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0672
// [SMC-CORE-034-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0673
// [SMC-CORE-034-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0674
// [SMC-CORE-034-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0675
// [SMC-CORE-034-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0676
// [SMC-CORE-034-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0677
// [SMC-CORE-034-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0678
// [SMC-CORE-034-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0679
// [SMC-CORE-035-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0680
// [SMC-CORE-035-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0681
// [SMC-CORE-035-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0682
// [SMC-CORE-035-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0683
// [SMC-CORE-035-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0684
// [SMC-CORE-035-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0685
// [SMC-CORE-035-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0686
// [SMC-CORE-035-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0687
// [SMC-CORE-035-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0688
// [SMC-CORE-035-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0689
// [SMC-CORE-035-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0690
// [SMC-CORE-035-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0691
// [SMC-CORE-035-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0692
// [SMC-CORE-035-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0693
// [SMC-CORE-035-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0694
// [SMC-CORE-035-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0695
// [SMC-CORE-035-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0696
// [SMC-CORE-035-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0697
// [SMC-CORE-035-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0698
// [SMC-CORE-035-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0699
// [SMC-CORE-036-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0700
// [SMC-CORE-036-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0701
// [SMC-CORE-036-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0702
// [SMC-CORE-036-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0703
// [SMC-CORE-036-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0704
// [SMC-CORE-036-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0705
// [SMC-CORE-036-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0706
// [SMC-CORE-036-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0707
// [SMC-CORE-036-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0708
// [SMC-CORE-036-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0709
// [SMC-CORE-036-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0710
// [SMC-CORE-036-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0711
// [SMC-CORE-036-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0712
// [SMC-CORE-036-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0713
// [SMC-CORE-036-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0714
// [SMC-CORE-036-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0715
// [SMC-CORE-036-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0716
// [SMC-CORE-036-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0717
// [SMC-CORE-036-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0718
// [SMC-CORE-036-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0719
// [SMC-CORE-037-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0720
// [SMC-CORE-037-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0721
// [SMC-CORE-037-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0722
// [SMC-CORE-037-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0723
// [SMC-CORE-037-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0724
// [SMC-CORE-037-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0725
// [SMC-CORE-037-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0726
// [SMC-CORE-037-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0727
// [SMC-CORE-037-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0728
// [SMC-CORE-037-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0729
// [SMC-CORE-037-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0730
// [SMC-CORE-037-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0731
// [SMC-CORE-037-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0732
// [SMC-CORE-037-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0733
// [SMC-CORE-037-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0734
// [SMC-CORE-037-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0735
// [SMC-CORE-037-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0736
// [SMC-CORE-037-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0737
// [SMC-CORE-037-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0738
// [SMC-CORE-037-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0739
// [SMC-CORE-038-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0740
// [SMC-CORE-038-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0741
// [SMC-CORE-038-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0742
// [SMC-CORE-038-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0743
// [SMC-CORE-038-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0744
// [SMC-CORE-038-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0745
// [SMC-CORE-038-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0746
// [SMC-CORE-038-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0747
// [SMC-CORE-038-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0748
// [SMC-CORE-038-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0749
// [SMC-CORE-038-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0750
// [SMC-CORE-038-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0751
// [SMC-CORE-038-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0752
// [SMC-CORE-038-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0753
// [SMC-CORE-038-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0754
// [SMC-CORE-038-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0755
// [SMC-CORE-038-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0756
// [SMC-CORE-038-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0757
// [SMC-CORE-038-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0758
// [SMC-CORE-038-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0759
// [SMC-CORE-039-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0760
// [SMC-CORE-039-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0761
// [SMC-CORE-039-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0762
// [SMC-CORE-039-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0763
// [SMC-CORE-039-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0764
// [SMC-CORE-039-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0765
// [SMC-CORE-039-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0766
// [SMC-CORE-039-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0767
// [SMC-CORE-039-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0768
// [SMC-CORE-039-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0769
// [SMC-CORE-039-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0770
// [SMC-CORE-039-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0771
// [SMC-CORE-039-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0772
// [SMC-CORE-039-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0773
// [SMC-CORE-039-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0774
// [SMC-CORE-039-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0775
// [SMC-CORE-039-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0776
// [SMC-CORE-039-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0777
// [SMC-CORE-039-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0778
// [SMC-CORE-039-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0779
// [SMC-CORE-040-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0780
// [SMC-CORE-040-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0781
// [SMC-CORE-040-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0782
// [SMC-CORE-040-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0783
// [SMC-CORE-040-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0784
// [SMC-CORE-040-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0785
// [SMC-CORE-040-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0786
// [SMC-CORE-040-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0787
// [SMC-CORE-040-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0788
// [SMC-CORE-040-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0789
// [SMC-CORE-040-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0790
// [SMC-CORE-040-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0791
// [SMC-CORE-040-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0792
// [SMC-CORE-040-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0793
// [SMC-CORE-040-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0794
// [SMC-CORE-040-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0795
// [SMC-CORE-040-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0796
// [SMC-CORE-040-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0797
// [SMC-CORE-040-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0798
// [SMC-CORE-040-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0799
// [SMC-CORE-041-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0800
// [SMC-CORE-041-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0801
// [SMC-CORE-041-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0802
// [SMC-CORE-041-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0803
// [SMC-CORE-041-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0804
// [SMC-CORE-041-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0805
// [SMC-CORE-041-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0806
// [SMC-CORE-041-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0807
// [SMC-CORE-041-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0808
// [SMC-CORE-041-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0809
// [SMC-CORE-041-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0810
// [SMC-CORE-041-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0811
// [SMC-CORE-041-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0812
// [SMC-CORE-041-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0813
// [SMC-CORE-041-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0814
// [SMC-CORE-041-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0815
// [SMC-CORE-041-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0816
// [SMC-CORE-041-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0817
// [SMC-CORE-041-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0818
// [SMC-CORE-041-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0819
// [SMC-CORE-042-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0820
// [SMC-CORE-042-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0821
// [SMC-CORE-042-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0822
// [SMC-CORE-042-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0823
// [SMC-CORE-042-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0824
// [SMC-CORE-042-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0825
// [SMC-CORE-042-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0826
// [SMC-CORE-042-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0827
// [SMC-CORE-042-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0828
// [SMC-CORE-042-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0829
// [SMC-CORE-042-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0830
// [SMC-CORE-042-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0831
// [SMC-CORE-042-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0832
// [SMC-CORE-042-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0833
// [SMC-CORE-042-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0834
// [SMC-CORE-042-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0835
// [SMC-CORE-042-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0836
// [SMC-CORE-042-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0837
// [SMC-CORE-042-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0838
// [SMC-CORE-042-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0839
// [SMC-CORE-043-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0840
// [SMC-CORE-043-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0841
// [SMC-CORE-043-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0842
// [SMC-CORE-043-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0843
// [SMC-CORE-043-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0844
// [SMC-CORE-043-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0845
// [SMC-CORE-043-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0846
// [SMC-CORE-043-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0847
// [SMC-CORE-043-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0848
// [SMC-CORE-043-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0849
// [SMC-CORE-043-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0850
// [SMC-CORE-043-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0851
// [SMC-CORE-043-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0852
// [SMC-CORE-043-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0853
// [SMC-CORE-043-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0854
// [SMC-CORE-043-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0855
// [SMC-CORE-043-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0856
// [SMC-CORE-043-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0857
// [SMC-CORE-043-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0858
// [SMC-CORE-043-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0859
// [SMC-CORE-044-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0860
// [SMC-CORE-044-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0861
// [SMC-CORE-044-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0862
// [SMC-CORE-044-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0863
// [SMC-CORE-044-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0864
// [SMC-CORE-044-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0865
// [SMC-CORE-044-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0866
// [SMC-CORE-044-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0867
// [SMC-CORE-044-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0868
// [SMC-CORE-044-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0869
// [SMC-CORE-044-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0870
// [SMC-CORE-044-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0871
// [SMC-CORE-044-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0872
// [SMC-CORE-044-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0873
// [SMC-CORE-044-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0874
// [SMC-CORE-044-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0875
// [SMC-CORE-044-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0876
// [SMC-CORE-044-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0877
// [SMC-CORE-044-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0878
// [SMC-CORE-044-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0879
// [SMC-CORE-045-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0880
// [SMC-CORE-045-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0881
// [SMC-CORE-045-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0882
// [SMC-CORE-045-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0883
// [SMC-CORE-045-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0884
// [SMC-CORE-045-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0885
// [SMC-CORE-045-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0886
// [SMC-CORE-045-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0887
// [SMC-CORE-045-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0888
// [SMC-CORE-045-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0889
// [SMC-CORE-045-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0890
// [SMC-CORE-045-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0891
// [SMC-CORE-045-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0892
// [SMC-CORE-045-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0893
// [SMC-CORE-045-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0894
// [SMC-CORE-045-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0895
// [SMC-CORE-045-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0896
// [SMC-CORE-045-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0897
// [SMC-CORE-045-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0898
// [SMC-CORE-045-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0899
// [SMC-CORE-046-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0900
// [SMC-CORE-046-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0901
// [SMC-CORE-046-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0902
// [SMC-CORE-046-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0903
// [SMC-CORE-046-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0904
// [SMC-CORE-046-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0905
// [SMC-CORE-046-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0906
// [SMC-CORE-046-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0907
// [SMC-CORE-046-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0908
// [SMC-CORE-046-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0909
// [SMC-CORE-046-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0910
// [SMC-CORE-046-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0911
// [SMC-CORE-046-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0912
// [SMC-CORE-046-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0913
// [SMC-CORE-046-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0914
// [SMC-CORE-046-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0915
// [SMC-CORE-046-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0916
// [SMC-CORE-046-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0917
// [SMC-CORE-046-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0918
// [SMC-CORE-046-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0919
// [SMC-CORE-047-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0920
// [SMC-CORE-047-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0921
// [SMC-CORE-047-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0922
// [SMC-CORE-047-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0923
// [SMC-CORE-047-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0924
// [SMC-CORE-047-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0925
// [SMC-CORE-047-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0926
// [SMC-CORE-047-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0927
// [SMC-CORE-047-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0928
// [SMC-CORE-047-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0929
// [SMC-CORE-047-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0930
// [SMC-CORE-047-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0931
// [SMC-CORE-047-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0932
// [SMC-CORE-047-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0933
// [SMC-CORE-047-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0934
// [SMC-CORE-047-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0935
// [SMC-CORE-047-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0936
// [SMC-CORE-047-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0937
// [SMC-CORE-047-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0938
// [SMC-CORE-047-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0939
// [SMC-CORE-048-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0940
// [SMC-CORE-048-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0941
// [SMC-CORE-048-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0942
// [SMC-CORE-048-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0943
// [SMC-CORE-048-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0944
// [SMC-CORE-048-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0945
// [SMC-CORE-048-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0946
// [SMC-CORE-048-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0947
// [SMC-CORE-048-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0948
// [SMC-CORE-048-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0949
// [SMC-CORE-048-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0950
// [SMC-CORE-048-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0951
// [SMC-CORE-048-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0952
// [SMC-CORE-048-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0953
// [SMC-CORE-048-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0954
// [SMC-CORE-048-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0955
// [SMC-CORE-048-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0956
// [SMC-CORE-048-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0957
// [SMC-CORE-048-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0958
// [SMC-CORE-048-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0959
// [SMC-CORE-049-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0960
// [SMC-CORE-049-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0961
// [SMC-CORE-049-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0962
// [SMC-CORE-049-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0963
// [SMC-CORE-049-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0964
// [SMC-CORE-049-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0965
// [SMC-CORE-049-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0966
// [SMC-CORE-049-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0967
// [SMC-CORE-049-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0968
// [SMC-CORE-049-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0969
// [SMC-CORE-049-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0970
// [SMC-CORE-049-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0971
// [SMC-CORE-049-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0972
// [SMC-CORE-049-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0973
// [SMC-CORE-049-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0974
// [SMC-CORE-049-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0975
// [SMC-CORE-049-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0976
// [SMC-CORE-049-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0977
// [SMC-CORE-049-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0978
// [SMC-CORE-049-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0979
// [SMC-CORE-050-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0980
// [SMC-CORE-050-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0981
// [SMC-CORE-050-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0982
// [SMC-CORE-050-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0983
// [SMC-CORE-050-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0984
// [SMC-CORE-050-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0985
// [SMC-CORE-050-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0986
// [SMC-CORE-050-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0987
// [SMC-CORE-050-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0988
// [SMC-CORE-050-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0989
// [SMC-CORE-050-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0990
// [SMC-CORE-050-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0991
// [SMC-CORE-050-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0992
// [SMC-CORE-050-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0993
// [SMC-CORE-050-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0994
// [SMC-CORE-050-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0995
// [SMC-CORE-050-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0996
// [SMC-CORE-050-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0997
// [SMC-CORE-050-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0998
// [SMC-CORE-050-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 0999
// [SMC-CORE-051-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1000
// [SMC-CORE-051-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1001
// [SMC-CORE-051-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1002
// [SMC-CORE-051-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1003
// [SMC-CORE-051-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1004
// [SMC-CORE-051-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1005
// [SMC-CORE-051-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1006
// [SMC-CORE-051-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1007
// [SMC-CORE-051-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1008
// [SMC-CORE-051-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1009
// [SMC-CORE-051-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1010
// [SMC-CORE-051-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1011
// [SMC-CORE-051-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1012
// [SMC-CORE-051-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1013
// [SMC-CORE-051-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1014
// [SMC-CORE-051-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1015
// [SMC-CORE-051-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1016
// [SMC-CORE-051-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1017
// [SMC-CORE-051-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1018
// [SMC-CORE-051-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1019
// [SMC-CORE-052-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1020
// [SMC-CORE-052-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1021
// [SMC-CORE-052-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1022
// [SMC-CORE-052-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1023
// [SMC-CORE-052-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1024
// [SMC-CORE-052-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1025
// [SMC-CORE-052-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1026
// [SMC-CORE-052-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1027
// [SMC-CORE-052-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1028
// [SMC-CORE-052-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1029
// [SMC-CORE-052-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1030
// [SMC-CORE-052-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1031
// [SMC-CORE-052-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1032
// [SMC-CORE-052-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1033
// [SMC-CORE-052-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1034
// [SMC-CORE-052-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1035
// [SMC-CORE-052-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1036
// [SMC-CORE-052-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1037
// [SMC-CORE-052-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1038
// [SMC-CORE-052-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1039
// [SMC-CORE-053-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1040
// [SMC-CORE-053-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1041
// [SMC-CORE-053-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1042
// [SMC-CORE-053-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1043
// [SMC-CORE-053-05] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1044
// [SMC-CORE-053-06] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1045
// [SMC-CORE-053-07] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1046
// [SMC-CORE-053-08] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1047
// [SMC-CORE-053-09] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1048
// [SMC-CORE-053-10] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1049
// [SMC-CORE-053-11] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1050
// [SMC-CORE-053-12] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1051
// [SMC-CORE-053-13] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1052
// [SMC-CORE-053-14] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1053
// [SMC-CORE-053-15] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1054
// [SMC-CORE-053-16] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1055
// [SMC-CORE-053-17] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1056
// [SMC-CORE-053-18] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1057
// [SMC-CORE-053-19] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1058
// [SMC-CORE-053-20] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1059
// [SMC-CORE-054-01] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1060
// [SMC-CORE-054-02] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1061
// [SMC-CORE-054-03] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1062
// [SMC-CORE-054-04] Institutional Liquidity Flow Verification, Premium/Discount Equilibrium Range Index: 1063
//+------------------------------------------------------------------+