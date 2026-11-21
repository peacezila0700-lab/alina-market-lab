//+------------------------------------------------------------------+
//|                                G7_Trade_Manager_Prop_Guard.mq5   |
//|                                  Copyright 2026, G7 Trading Team |
//|                                             https://www.mql5.com |
//+------------------------------------------------------------------+
#property copyright   "Copyright 2026, G7 Trading Team"
#property link        "https://www.mql5.com"
#property version     "1.30"
#property description "G7 Pro Trade Manager & Prop Firm Equity Protector"
#property description "Spacious Obsidian HUD, 1-Click Execution, Auto Breakeven & Prop DD Circuit Breaker."

#include <Trade\Trade.mqh>
#include <Trade\PositionInfo.mqh>
#include <Trade\AccountInfo.mqh>
#include <Trade\SymbolInfo.mqh>

//--- Input Groups
#define GROUP_EXEC    "=== 1. FAST ONE-CLICK EXECUTION ==="
#define GROUP_BE      "=== 2. AUTO BREAKEVEN SHIELD ==="
#define GROUP_TRAIL   "=== 3. DYNAMIC TRAILING STOP ==="
#define GROUP_PROP    "=== 4. PROP FIRM EQUITY CIRCUIT BREAKER ==="
#define GROUP_UI      "=== 5. ON-CHART HUD DASHBOARD ==="

//--- 1. Execution Inputs
input group GROUP_EXEC
input double InpDefaultLot          = 0.01;       // Default Order Lot Size
input double InpDefaultSL_Pips      = 25.0;       // Default Stop Loss (Pips, 0=None)
input double InpDefaultTP_Pips      = 50.0;       // Default Take Profit (Pips, 0=None)
input ulong  InpMagicNumber         = 0;          // Magic Number (0 = Manage ALL Trades)
input bool   InpCurrentSymbolOnly   = true;       // Manage Current Symbol Only

//--- 2. Breakeven Inputs
input group GROUP_BE
input bool   InpEnableAutoBE        = true;       // Enable Auto Breakeven Shield
input double InpBETriggerPips       = 15.0;       // Breakeven Activation (Pips in Profit)
input double InpBELockPips          = 3.0;        // Locked Profit Pips Above Entry

//--- 3. Trailing Stop Inputs
input group GROUP_TRAIL
input bool   InpEnableTrailing      = true;       // Enable Dynamic Trailing Stop
input double InpTrailingStartPips   = 20.0;       // Trailing Start Activation (Pips)
input double InpTrailingDistPips    = 15.0;       // Trailing Distance Behind Price (Pips)
input double InpTrailingStepPips    = 3.0;        // Trailing Step Distance (Pips)

//--- 4. Prop Firm Inputs
input group GROUP_PROP
input bool   InpEnablePropGuard     = true;       // Enable Prop Firm Daily DD Shield
input double InpMaxDailyLossPct     = 4.0;        // Max Daily Loss % (Emergency Kill Switch)
input double InpMaxDailyProfitPct   = 8.0;        // Max Daily Target % (Lock Daily Win)
input bool   InpEmergencyCloseAll   = true;       // Auto Close All Trades On DD Breach

//--- 5. UI Inputs
input group GROUP_UI
input bool   InpShowDashboard       = true;       // Show On-Chart Glassmorphism Panel
input ENUM_BASE_CORNER InpPanelCorner= CORNER_LEFT_UPPER; // Panel Corner (Top-Left or Top-Right)
input int    InpPanelX              = 20;         // Panel X Offset
input int    InpPanelY              = 115;        // Panel Y Offset (Cleanly Below MT5 Quick Trading Box)

//--- Global Variables & Classes
CTrade         m_trade;
CPositionInfo  m_position;
CAccountInfo   m_account;
CSymbolInfo    m_symbol;

datetime       g_lastDayReset       = 0;
double         g_dayStartBalance    = 0.0;
double         g_dayStartEquity     = 0.0;
bool           g_circuitBreakerHit  = false;
string         g_circuitReason      = "";

//--- Interactive Runtime State
double         g_currentLot         = 0.01;
bool           g_autoBEActive       = true;
bool           g_trailingActive     = true;

//--- Unique UI Prefix
#define UI_PREFIX "G7HUD_"

//+------------------------------------------------------------------+
//| Get Pip Size for any symbol                                      |
//+------------------------------------------------------------------+
double GetPipSize(const string sym)
{
   double point = SymbolInfoDouble(sym, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   if(digits == 3 || digits == 5) return point * 10.0;
   return point;
}

//+------------------------------------------------------------------+
//| Reset Daily Reference Balance                                    |
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
//| Calculate Floating Profit & Loss & Position Count                |
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
         if(InpMagicNumber > 0 && m_position.Magic() != InpMagicNumber) continue;
         totalFloating += m_position.Profit() + m_position.Swap();
         openCount++;
      }
   }
   return totalFloating;
}

//+------------------------------------------------------------------+
//| Check Prop Firm Circuit Breaker                                  |
//+------------------------------------------------------------------+
void CheckPropFirmGuard()
{
   if(!InpEnablePropGuard || g_circuitBreakerHit) return;

   double currentEquity = AccountInfoDouble(ACCOUNT_EQUITY);
   double baseline = (g_dayStartBalance > 0.0) ? g_dayStartBalance : currentEquity;
   if(baseline <= 0.0) return;

   double dailyNetChange = currentEquity - baseline;
   double dailyNetPct    = (dailyNetChange / baseline) * 100.0;

   // 1. Max Daily Loss Hit
   if(dailyNetPct <= -MathAbs(InpMaxDailyLossPct))
   {
      g_circuitBreakerHit = true;
      g_circuitReason = StringFormat("MAX DAILY LOSS HIT: %.2f%% (Limit: -%.2f%%)", dailyNetPct, InpMaxDailyLossPct);
      Alert(StringFormat("[G7 PROP GUARD] EMERGENCY SHUTDOWN: %s", g_circuitReason));

      if(InpEmergencyCloseAll)
      {
         CloseAllPositions();
      }
      return;
   }

   // 2. Max Daily Profit Target Reached
   if(InpMaxDailyProfitPct > 0.0 && dailyNetPct >= InpMaxDailyProfitPct)
   {
      g_circuitBreakerHit = true;
      g_circuitReason = StringFormat("DAILY TARGET ACHIEVED: +%.2f%% (Target: +%.2f%%)", dailyNetPct, InpMaxDailyProfitPct);
      Alert(StringFormat("[G7 PROP GUARD] TARGET SECURED: %s", g_circuitReason));

      if(InpEmergencyCloseAll)
      {
         CloseAllPositions();
      }
   }
}

//+------------------------------------------------------------------+
//| Close All Positions                                              |
//+------------------------------------------------------------------+
void CloseAllPositions(const string sym = "")
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         if(sym != "" && m_position.Symbol() != sym) continue;
         if(InpMagicNumber > 0 && m_position.Magic() != InpMagicNumber) continue;
         m_trade.PositionClose(m_position.Ticket());
      }
   }
}

//+------------------------------------------------------------------+
//| Close Only Winning Positions                                     |
//+------------------------------------------------------------------+
void CloseProfitablePositions(const string sym = "")
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         if(sym != "" && m_position.Symbol() != sym) continue;
         if(InpMagicNumber > 0 && m_position.Magic() != InpMagicNumber) continue;
         if(m_position.Profit() > 0.0)
         {
            m_trade.PositionClose(m_position.Ticket());
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Close 50% Partial Volume on All Positions                        |
//+------------------------------------------------------------------+
void ClosePartialFiftyPercent(const string sym = "")
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         if(sym != "" && m_position.Symbol() != sym) continue;
         if(InpMagicNumber > 0 && m_position.Magic() != InpMagicNumber) continue;

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

//+------------------------------------------------------------------+
//| Apply Breakeven to All Eligible Positions                        |
//+------------------------------------------------------------------+
void BreakevenAllPositions(bool forceNow = false)
{
   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         string sym = m_position.Symbol();
         if(InpCurrentSymbolOnly && sym != _Symbol) continue;
         if(InpMagicNumber > 0 && m_position.Magic() != InpMagicNumber) continue;

         double pip = GetPipSize(sym);
         double openPrice = m_position.PriceOpen();
         double currentSL = m_position.StopLoss();
         ENUM_POSITION_TYPE pType = m_position.PositionType();

         if(pType == POSITION_TYPE_BUY)
         {
            double bid = SymbolInfoDouble(sym, SYMBOL_BID);
            double profitPips = (bid - openPrice) / pip;

            if(forceNow || profitPips >= InpBETriggerPips)
            {
               double newSL = NormalizeDouble(openPrice + (InpBELockPips * pip), (int)SymbolInfoInteger(sym, SYMBOL_DIGITS));
               if(currentSL < newSL || currentSL == 0.0)
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
               double newSL = NormalizeDouble(openPrice - (InpBELockPips * pip), (int)SymbolInfoInteger(sym, SYMBOL_DIGITS));
               if(currentSL > newSL || currentSL == 0.0)
               {
                  m_trade.PositionModify(m_position.Ticket(), newSL, m_position.TakeProfit());
               }
            }
         }
      }
   }
}

//+------------------------------------------------------------------+
//| Dynamic Trailing Stop Engine                                     |
//+------------------------------------------------------------------+
void ProcessTrailingStop()
{
   if(!g_trailingActive) return;

   for(int i = PositionsTotal() - 1; i >= 0; i--)
   {
      if(m_position.SelectByIndex(i))
      {
         string sym = m_position.Symbol();
         if(InpCurrentSymbolOnly && sym != _Symbol) continue;
         if(InpMagicNumber > 0 && m_position.Magic() != InpMagicNumber) continue;

         double pip = GetPipSize(sym);
         int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
         double openPrice = m_position.PriceOpen();
         double currentSL = m_position.StopLoss();
         ENUM_POSITION_TYPE pType = m_position.PositionType();

         if(pType == POSITION_TYPE_BUY)
         {
            double bid = SymbolInfoDouble(sym, SYMBOL_BID);
            double profitPips = (bid - openPrice) / pip;

            if(profitPips >= InpTrailingStartPips)
            {
               double proposedSL = NormalizeDouble(bid - (InpTrailingDistPips * pip), digits);
               if(proposedSL > currentSL + (InpTrailingStepPips * pip) || currentSL == 0.0)
               {
                  if(proposedSL > openPrice)
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
               if(proposedSL < currentSL - (InpTrailingStepPips * pip) || currentSL == 0.0)
               {
                  if(proposedSL < openPrice)
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
//| Execute Fast One-Click Order                                     |
//+------------------------------------------------------------------+
void ExecuteFastOrder(ENUM_ORDER_TYPE orderType)
{
   if(g_circuitBreakerHit)
   {
      Alert("[G7 BLOCKED] Trading locked today by Prop Firm Shield: " + g_circuitReason);
      return;
   }

   string sym = _Symbol;
   double pip = GetPipSize(sym);
   int digits = (int)SymbolInfoInteger(sym, SYMBOL_DIGITS);
   double lot = g_currentLot;

   m_trade.SetExpertMagicNumber(InpMagicNumber);
   m_trade.SetDeviationInPoints(20);

   if(orderType == ORDER_TYPE_BUY)
   {
      double ask = SymbolInfoDouble(sym, SYMBOL_ASK);
      double sl = (InpDefaultSL_Pips > 0) ? NormalizeDouble(ask - (InpDefaultSL_Pips * pip), digits) : 0.0;
      double tp = (InpDefaultTP_Pips > 0) ? NormalizeDouble(ask + (InpDefaultTP_Pips * pip), digits) : 0.0;
      m_trade.Buy(lot, sym, ask, sl, tp, "G7 Trade Manager");
   }
   else if(orderType == ORDER_TYPE_SELL)
   {
      double bid = SymbolInfoDouble(sym, SYMBOL_BID);
      double sl = (InpDefaultSL_Pips > 0) ? NormalizeDouble(bid + (InpDefaultSL_Pips * pip), digits) : 0.0;
      double tp = (InpDefaultTP_Pips > 0) ? NormalizeDouble(bid - (InpDefaultTP_Pips * pip), digits) : 0.0;
      m_trade.Sell(lot, sym, bid, sl, tp, "G7 Trade Manager");
   }
}

//+------------------------------------------------------------------+
//| UI Primitive Helpers                                             |
//+------------------------------------------------------------------+
void UI_Button(string name, int x, int y, int w, int h, string text, color bgColor, color txtColor, int fontSize = 8, bool bold = true)
{
   string objName = UI_PREFIX + name;
   if(ObjectFind(0, objName) < 0)
   {
      ObjectCreate(0, objName, OBJ_BUTTON, 0, 0, 0);
      ObjectSetInteger(0, objName, OBJPROP_CORNER, InpPanelCorner);
      ObjectSetInteger(0, objName, OBJPROP_SELECTABLE, false);
      ObjectSetString(0, objName, OBJPROP_FONT, bold ? "Arial Bold" : "Arial");
   }
   ObjectSetInteger(0, objName, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, objName, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, objName, OBJPROP_XSIZE, w);
   ObjectSetInteger(0, objName, OBJPROP_YSIZE, h);
   ObjectSetInteger(0, objName, OBJPROP_FONTSIZE, fontSize);
   ObjectSetString(0, objName, OBJPROP_TEXT, text);
   ObjectSetInteger(0, objName, OBJPROP_BGCOLOR, bgColor);
   ObjectSetInteger(0, objName, OBJPROP_COLOR, txtColor);
   ObjectSetInteger(0, objName, OBJPROP_BORDER_COLOR, C'50,65,85');
   ObjectSetInteger(0, objName, OBJPROP_STATE, false);
}

void UI_Label(string name, int x, int y, string text, color txtColor, int fontSize = 8, bool bold = false)
{
   string objName = UI_PREFIX + name;
   if(ObjectFind(0, objName) < 0)
   {
      ObjectCreate(0, objName, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, objName, OBJPROP_CORNER, InpPanelCorner);
      ObjectSetInteger(0, objName, OBJPROP_SELECTABLE, false);
      ObjectSetString(0, objName, OBJPROP_FONT, bold ? "Arial Bold" : "Arial");
   }
   ObjectSetInteger(0, objName, OBJPROP_XDISTANCE, x);
   ObjectSetInteger(0, objName, OBJPROP_YDISTANCE, y);
   ObjectSetInteger(0, objName, OBJPROP_FONTSIZE, fontSize);
   ObjectSetString(0, objName, OBJPROP_TEXT, text);
   ObjectSetInteger(0, objName, OBJPROP_COLOR, txtColor);
}

void UI_Box(string name, int x, int y, int w, int h, color bgColor, color borderColor)
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
   ObjectSetInteger(0, objName, OBJPROP_BORDER_TYPE, BORDER_FLAT);
}

//+------------------------------------------------------------------+
//| Master Dashboard Purge (Deletes ALL G7/TM objects completely)    |
//+------------------------------------------------------------------+
void PurgeAllDashboardObjects()
{
   ObjectsDeleteAll(0, "G7_", 0, -1);
   ObjectsDeleteAll(0, "G7PRO_", 0, -1);
   ObjectsDeleteAll(0, "G7HUD_", 0, -1);
   ObjectsDeleteAll(0, "TM_", 0, -1);

   for(int i = ObjectsTotal(0, 0, -1) - 1; i >= 0; i--)
   {
      string name = ObjectName(0, i, 0, -1);
      if(StringFind(name, "G7") >= 0 || StringFind(name, "TM") >= 0 || StringFind(name, "HUD") >= 0)
      {
         ObjectDelete(0, name);
      }
   }
   ChartRedraw(0);
}

//+------------------------------------------------------------------+
//| Render Complete Obsidian Glassmorphism Dashboard                |
//+------------------------------------------------------------------+
void RenderDashboard()
{
   if(!InpShowDashboard) return;

   int px = InpPanelX;
   int py = InpPanelY;
   int pw = 380;
   int ph = 400;

   // 1. Background Main Frame & Header
   UI_Box("BG_FRAME", px, py, pw, ph, C'14,18,25', C'42,56,76');
   UI_Box("HEADER_FRAME", px, py, pw, 34, C'20,28,42', C'0,180,216');

   // Header Title & Version Badge
   UI_Label("HDR_TITLE", px + 14, py + 9, "⚡ G7 PRO TRADE MANAGER & GUARD", C'0,220,255', 9, true);
   UI_Label("HDR_VER", px + 335, py + 10, "v1.30", C'255,215,0', 8, true);

   // 2. Section A: Account Health & Prop Guard Card (Height: 76px)
   int curY = py + 42;
   UI_Box("CARD_ACCOUNT", px + 12, curY, pw - 24, 76, C'20,26,36', C'32,44,62');

   double balance = AccountInfoDouble(ACCOUNT_BALANCE);
   double equity  = AccountInfoDouble(ACCOUNT_EQUITY);
   int openTrades = 0;
   double floatPnL = GetFloatingPnL(InpCurrentSymbolOnly ? _Symbol : "", openTrades);
   double baseline = (g_dayStartBalance > 0.0) ? g_dayStartBalance : balance;
   double dailyNetPct = (baseline > 0.0) ? ((equity - baseline) / baseline) * 100.0 : 0.0;

   color floatCol = (floatPnL >= 0) ? C'0,230,118' : C'255,82,82';
   color dailyCol = (dailyNetPct >= 0) ? C'0,230,118' : C'255,82,82';

   // Row 1: Balance & Equity (Generous 185px separation)
   UI_Label("L_BAL", px + 20, curY + 8, StringFormat("Balance: $%.2f", balance), C'170,185,205', 8);
   UI_Label("L_EQT", px + 205, curY + 8, StringFormat("Equity: $%.2f", equity), C'255,255,255', 8, true);

   // Row 2: Floating & Daily Net %
   UI_Label("L_FLOAT", px + 20, curY + 30, StringFormat("Floating: %s$%.2f", (floatPnL>=0?"+":""), floatPnL), floatCol, 8, true);
   UI_Label("L_DAILY", px + 205, curY + 30, StringFormat("Daily Net: %s%.2f%%", (dailyNetPct>=0?"+":""), dailyNetPct), dailyCol, 8, true);

   // Row 3: Prop Guard Status
   string guardStatus = g_circuitBreakerHit ? "PROP GUARD: [BREACHED - TRADING LOCKED]" : StringFormat("Prop Guard: -%.1f%% Max Loss (PROTECTED)", InpMaxDailyLossPct);
   color guardStatusCol = g_circuitBreakerHit ? C'255,50,50' : C'0,230,118';
   UI_Label("L_GUARD_ST", px + 20, curY + 54, guardStatus, guardStatusCol, 7, true);

   // 3. Section B: Live Market Bar (Height: 28px)
   curY += 84;
   UI_Box("CARD_MARKET", px + 12, curY, pw - 24, 28, C'18,23,32', C'30,40,56');

   long spreadPts = SymbolInfoInteger(_Symbol, SYMBOL_SPREAD);
   double spreadPips = (double)spreadPts * SymbolInfoDouble(_Symbol, SYMBOL_POINT) / GetPipSize(_Symbol);
   color spdCol = (spreadPips <= 2.5) ? C'0,230,118' : (spreadPips <= 5.0 ? C'255,215,0' : C'255,82,82');

   UI_Label("L_SYM", px + 20, curY + 7, StringFormat("Pair: %s", _Symbol), C'200,215,235', 8, true);
   UI_Label("L_SPD", px + 155, curY + 7, StringFormat("Spread: %.1fp", spreadPips), spdCol, 8, true);
   UI_Label("L_TRD", px + 265, curY + 7, StringFormat("Open: %d Trades", openTrades), C'255,255,255', 8);

   // 4. Section C: Interactive Lot & SL/TP Sizer (Height: 36px)
   curY += 36;
   UI_Box("CARD_LOT_BOX", px + 12, curY, pw - 24, 36, C'20,26,38', C'32,44,62');

   UI_Button("BTN_LOT_MINUS", px + 18, curY + 5, 32, 26, "-", C'38,48,68', C'255,255,255', 10, true);
   UI_Label("L_LOT_VAL", px + 62, curY + 10, StringFormat("LOT: %.2f", g_currentLot), C'0,225,255', 9, true);
   UI_Button("BTN_LOT_PLUS", px + 148, curY + 5, 32, 26, "+", C'38,48,68', C'255,255,255', 10, true);

   string sltpTxt = StringFormat("SL: %.0fp   |   TP: %.0fp", InpDefaultSL_Pips, InpDefaultTP_Pips);
   UI_Label("L_SLTP", px + 205, curY + 10, sltpTxt, C'165,180,200', 8);

   // 5. Section D: One-Click Primary Execution (Buy / Sell - 172px each)
   curY += 44;
   int btnW = 172;
   UI_Button("BTN_BUY", px + 12, curY, btnW, 40, "▲ BUY", C'0,150,70', C'255,255,255', 11, true);
   UI_Button("BTN_SELL", px + 196, curY, btnW, 40, "▼ SELL", C'195,30,40', C'255,255,255', 11, true);

   // 6. Section E: Position Management (2x2 Grid - 172px each)
   curY += 46;
   UI_Button("BTN_BE", px + 12, curY, btnW, 28, "⚡ BREAKEVEN ALL", C'24,65,120', C'220,240,255', 8, true);
   UI_Button("BTN_HALF", px + 196, curY, btnW, 28, "½ CLOSE 50%", C'175,105,20', C'255,255,255', 8, true);

   curY += 34;
   UI_Button("BTN_CLOSE_WIN", px + 12, curY, btnW, 28, "✔ CLOSE PROFIT", C'18,100,75', C'220,255,235', 8, true);
   UI_Button("BTN_CLOSE_ALL", px + 196, curY, btnW, 28, "✖ CLOSE ALL", C'135,22,32', C'255,220,220', 8, true);

   // 7. Section F: Interactive Automation Toggles (172px each)
   curY += 36;
   color beBg = g_autoBEActive ? C'18,85,115' : C'35,42,55';
   string beTxt = g_autoBEActive ? "Auto-BE: ON (+15p)" : "Auto-BE: OFF";
   UI_Button("BTN_TOGGLE_BE", px + 12, curY, btnW, 26, beTxt, beBg, C'255,255,255', 8);

   color trBg = g_trailingActive ? C'75,35,110' : C'35,42,55';
   string trTxt = g_trailingActive ? "Trailing: ON (+20p)" : "Trailing: OFF";
   UI_Button("BTN_TOGGLE_TRAIL", px + 196, curY, btnW, 26, trTxt, trBg, C'255,255,255', 8);

   // 8. Footer Brand Signature
   curY += 34;
   UI_Label("L_BRAND", px + 36, curY, "⚡ G7 QUANTUM ALGO • FREE COMMUNITY EDITION ⚡", C'0,180,216', 7, true);
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

   g_currentLot = InpDefaultLot;
   g_autoBEActive = InpEnableAutoBE;
   g_trailingActive = InpEnableTrailing;

   CheckDailyReset();
   EventSetTimer(1);

   // Purge all old chart remnants completely before building
   PurgeAllDashboardObjects();

   if(InpShowDashboard)
   {
      RenderDashboard();
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
//| ChartEvent function (Interactive One-Click UI)                   |
//+------------------------------------------------------------------+
void OnChartEvent(const int id,
                  const long &lparam,
                  const double &dparam,
                  const string &sparam)
{
   if(id == CHARTEVENT_OBJECT_CLICK)
   {
      // 1. Lot Selector Buttons
      if(sparam == UI_PREFIX + "BTN_LOT_MINUS")
      {
         double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
         double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
         g_currentLot = MathMax(minLot, NormalizeDouble(g_currentLot - step, 2));
         RenderDashboard();
         ChartRedraw(0);
         return;
      }
      else if(sparam == UI_PREFIX + "BTN_LOT_PLUS")
      {
         double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
         double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
         g_currentLot = MathMin(maxLot, NormalizeDouble(g_currentLot + step, 2));
         RenderDashboard();
         ChartRedraw(0);
         return;
      }

      // 2. Execution Buttons
      if(sparam == UI_PREFIX + "BTN_BUY")
      {
         ExecuteFastOrder(ORDER_TYPE_BUY);
         ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
         ChartRedraw(0);
      }
      else if(sparam == UI_PREFIX + "BTN_SELL")
      {
         ExecuteFastOrder(ORDER_TYPE_SELL);
         ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
         ChartRedraw(0);
      }

      // 3. Position Management Buttons
      else if(sparam == UI_PREFIX + "BTN_BE")
      {
         BreakevenAllPositions(true);
         ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
         ChartRedraw(0);
      }
      else if(sparam == UI_PREFIX + "BTN_HALF")
      {
         ClosePartialFiftyPercent(InpCurrentSymbolOnly ? _Symbol : "");
         ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
         ChartRedraw(0);
      }
      else if(sparam == UI_PREFIX + "BTN_CLOSE_WIN")
      {
         CloseProfitablePositions(InpCurrentSymbolOnly ? _Symbol : "");
         ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
         ChartRedraw(0);
      }
      else if(sparam == UI_PREFIX + "BTN_CLOSE_ALL")
      {
         CloseAllPositions(InpCurrentSymbolOnly ? _Symbol : "");
         ObjectSetInteger(0, sparam, OBJPROP_STATE, false);
         ChartRedraw(0);
      }

      // 4. Interactive Toggles
      else if(sparam == UI_PREFIX + "BTN_TOGGLE_BE")
      {
         g_autoBEActive = !g_autoBEActive;
         RenderDashboard();
         ChartRedraw(0);
      }
      else if(sparam == UI_PREFIX + "BTN_TOGGLE_TRAIL")
      {
         g_trailingActive = !g_trailingActive;
         RenderDashboard();
         ChartRedraw(0);
      }
   }
}
//+------------------------------------------------------------------+
