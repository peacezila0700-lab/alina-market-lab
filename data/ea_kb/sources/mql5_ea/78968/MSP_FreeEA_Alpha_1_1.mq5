//+------------------------------------------------------------------+
//|                                                    MSP Free EA 1 |
//|                                   Copyright 2026, MetaSignalsPro |
//|                                    http://www.MetaSignalsPro.com |
//+------------------------------------------------------------------+

// The #property lines below appear in the EA's Properties window and on its product page.
#property copyright "Click here to contact us and get support."
#property link "https://www.mql5.com/en/users/metasignalspro/seller"
#property version "1.0"
#property description "Asset: XAUUSD | Time Frame: M30"
#property description "MetaSignalsPro Free Expert Advisor"
#property description ""
#property description "MQL5.com is an authorized site to sell our products."
#property description "Sales on other sites not authorized by us are fraudulent, illegal and will be prosecuted by law."
#property description ""
#property description "Trade safe."
#property description ""
#property description "MetaSignalsPro | Making your trading easier, faster and safer."

// Standard library that provides the CTrade class used to send orders.
#include <Trade/Trade.mqh>

// Builds a "rejected" trade result and returns false.
// The same rejection is printed at most once per minute to avoid spamming the journal.
bool MetaMindSingleReject(MqlTradeResult &result, uint code, string reason)
  {
   ZeroMemory(result);
   result.retcode = code;
   result.comment = reason;
    
   static uint last_code = 0;
   static string last_reason = "";
   static datetime last_time = 0;
   datetime now = TimeCurrent();
   if(code != last_code || reason != last_reason || now - last_time >= 60)
     {
      PrintFormat("MetaMind trade skipped [%u]: %s", code, reason);
      last_code = code;
      last_reason = reason;
      last_time = now;
     }
   return false;
  }

// Returns true when this market order would reduce or fully close an existing
// opposite position (hedging accounts: matched by ticket, netting: by symbol).
// Such closing requests are allowed even when the account has insufficient margin.
bool MetaMindSingleReducesPosition(const MqlTradeRequest &request)
  {
   if(request.action != TRADE_ACTION_DEAL) return false;
    
   // Save the currently selected position; the checks below change the selection.
   ulong previous = (ulong)PositionGetInteger(POSITION_TICKET);
   bool selected = false;
   if(request.position > 0) selected = PositionSelectByTicket(request.position);
   else if(AccountInfoInteger(ACCOUNT_MARGIN_MODE) != ACCOUNT_MARGIN_MODE_RETAIL_HEDGING)
      selected = PositionSelect(request.symbol);
   bool reducing = selected && PositionGetString(POSITION_SYMBOL) == request.symbol
      && request.volume > 0.0 && request.volume <= PositionGetDouble(POSITION_VOLUME)
      && ((request.type == ORDER_TYPE_BUY && PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_SELL)
       || (request.type == ORDER_TYPE_SELL && PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY));
   if(previous > 0 && !PositionSelectByTicket(previous)) return reducing;
   return reducing;
  }

// True when a SL/TP update (position) or pending-order modification changes nothing,
// so the request can be skipped with TRADE_RETCODE_NO_CHANGES instead of hitting the server.
bool MetaMindSingleUnchanged(const MqlTradeRequest &request)
  {
   if(request.action == TRADE_ACTION_SLTP)
     {
      ulong previous = (ulong)PositionGetInteger(POSITION_TICKET);
      bool selected = request.position > 0 ? PositionSelectByTicket(request.position) : PositionSelect(request.symbol);
      bool unchanged = selected && request.sl == PositionGetDouble(POSITION_SL) && request.tp == PositionGetDouble(POSITION_TP);
      if(previous > 0 && !PositionSelectByTicket(previous)) return unchanged;
      return unchanged;
     }
   if(request.action == TRADE_ACTION_MODIFY)
     {
      ulong previous = (ulong)OrderGetInteger(ORDER_TICKET);
      bool selected = OrderSelect(request.order);
      bool unchanged = selected && request.price == OrderGetDouble(ORDER_PRICE_OPEN)
         && request.sl == OrderGetDouble(ORDER_SL) && request.tp == OrderGetDouble(ORDER_TP)
         && request.stoplimit == OrderGetDouble(ORDER_PRICE_STOPLIMIT)
         && request.type_time == (ENUM_ORDER_TYPE_TIME)OrderGetInteger(ORDER_TYPE_TIME)
         && request.expiration == (datetime)OrderGetInteger(ORDER_TIME_EXPIRATION);
      if(previous > 0 && !OrderSelect(previous)) return unchanged;
      return unchanged;
     }
   return false;
  }

// Validates a request before sending: skips no-change SL/TP edits, runs OrderCheck,
// allows closing trades even with low margin, blocks new orders if margin would go negative.
bool MetaMindSinglePreflight(const MqlTradeRequest &request, MqlTradeResult &result)
  {
   // True when the request removes/closes an order or reduces an open position.
   bool reducing = request.action == TRADE_ACTION_REMOVE || request.action == TRADE_ACTION_CLOSE_BY
      || MetaMindSingleReducesPosition(request);
   if(MetaMindSingleUnchanged(request)) return MetaMindSingleReject(result, TRADE_RETCODE_NO_CHANGES, "No change to order or position");
    
   MqlTradeCheckResult check = {};
   bool checked = OrderCheck(request, check);
   // Closing/reducing trades are allowed even if the broker reports NO_MONEY.
   if(reducing && check.retcode == TRADE_RETCODE_NO_MONEY) return true;
   if(!checked || (check.retcode != 0 && check.retcode != TRADE_RETCODE_DONE))
      return MetaMindSingleReject(result, check.retcode == 0 ? TRADE_RETCODE_ERROR : check.retcode,
         check.comment == "" ? "Trade request preflight failed" : check.comment);
   // New orders are blocked when the trade would leave negative free margin.
   if(!reducing && (request.action == TRADE_ACTION_DEAL || request.action == TRADE_ACTION_PENDING) && check.margin_free < 0.0)
      return MetaMindSingleReject(result, TRADE_RETCODE_NO_MONEY, "Insufficient free margin");
   return true;
  }

// Sends a synchronous order, but only if the preflight validation passes.
bool MetaMindSingleOrderSend(const MqlTradeRequest &request, MqlTradeResult &result)
  {
   if(!MetaMindSinglePreflight(request, result)) return false;
   return ::OrderSend(request, result);
  }

// Same as above, but the non-blocking (async) version of OrderSend.
bool MetaMindSingleOrderSendAsync(const MqlTradeRequest &request, MqlTradeResult &result)
  {
   if(!MetaMindSinglePreflight(request, result)) return false;
   return ::OrderSendAsync(request, result);
  }

// CTrade subclass that runs the preflight validation on EVERY order sent through it
// (Buy, Sell, PositionClose, OrderDelete, ...), so all trades are checked before sending.
class MetaMindSingleTrade : public CTrade
  {
protected:
   virtual bool OrderSend(const MqlTradeRequest &request, MqlTradeResult &result)
     {
      if(!MetaMindSinglePreflight(request, result)) return false;
      return CTrade::OrderSend(request, result);
     }
  };

// Trade.mqh is already included above; repeating the include is harmless.
#include <Trade/Trade.mqh>
// Global trade object used by the whole EA - every order goes through the preflight.
MetaMindSingleTrade trade;

// Magic number and comment tag: every order/position opened by this EA carries them,
// so the EA recognizes only its own trades and never touches trades from other EAs.
const int Magic = 568330;
const string StrategyComment = "EmaTrendCross_V1__XAUUSD_M30";

// --- User inputs: shown in the EA Properties dialog when attaching it to a chart ---

// EMA periods: fast/slow for the crossover signal, trend EMA as direction filter.
input int FastEmaPeriod = 20;
input int SlowEmaPeriod = 50;
input int TrendEmaPeriod = 200;
// Entry window in broker server time (default 07:00 - 19:00).
input int EntryStartHour = 7;
input int EntryStartMinute = 0;
input int EntryEndHour = 19;
input int EntryEndMinute = 0;
// Daily close-all time in broker server time (default 20:00).
input int ExitHour = 20;
input int ExitMinute = 0;
// Risk settings: % of balance risked per trade, SL distance in % of the entry price.
input double RiskPercent = 1;
input double StopLossPercent = 1;

// Open time of the last processed bar and the moment of the last daily exit.
datetime lastBarTime = 0;
datetime lastExitExecution = 0;
// Handles of the three EMA indicators created in OnInit.
int handleFastEma;
int handleSlowEma;
int handleTrendEma;

// Possible directions returned by the signal function.
enum SignalDirection
  {
   SIGNAL_NONE = 0,
   SIGNAL_BUY = 1,
   SIGNAL_SELL = 2
  };

// Runs once when the EA is attached to a chart.
// Validates the inputs, sets the magic number and creates the three EMA indicators.
// Returns INIT_PARAMETERS_INCORRECT when a setting is invalid (the EA will not start).
int OnInit()
  {
   if(RiskPercent <= 0.0 || StopLossPercent <= 0.0)
      return INIT_PARAMETERS_INCORRECT;

   if(FastEmaPeriod <= 0 || SlowEmaPeriod <= 0 || TrendEmaPeriod <= 0)
      return INIT_PARAMETERS_INCORRECT;
   if(FastEmaPeriod >= SlowEmaPeriod)
      return INIT_PARAMETERS_INCORRECT;

   if(EntryStartHour < 0 || EntryStartHour > 23 || EntryEndHour < 0 || EntryEndHour > 23 || ExitHour < 0 || ExitHour > 23)
      return INIT_PARAMETERS_INCORRECT;
   if(EntryStartMinute < 0 || EntryStartMinute > 59 || EntryEndMinute < 0 || EntryEndMinute > 59 || ExitMinute < 0 || ExitMinute > 59)
      return INIT_PARAMETERS_INCORRECT;

   trade.SetExpertMagicNumber(Magic);

   handleFastEma = iMA(_Symbol, PERIOD_CURRENT, FastEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   handleSlowEma = iMA(_Symbol, PERIOD_CURRENT, SlowEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);
   handleTrendEma = iMA(_Symbol, PERIOD_CURRENT, TrendEmaPeriod, 0, MODE_EMA, PRICE_CLOSE);

   return INIT_SUCCEEDED;
  }

// Runs when the EA is removed or the chart closes: frees the indicator handles.
void OnDeinit(const int reason)
  {
   IndicatorRelease(handleFastEma);
   IndicatorRelease(handleSlowEma);
   IndicatorRelease(handleTrendEma);
  }

// Returns true only on the first tick of a new bar.
// This makes the whole strategy evaluate signals once per bar instead of on every tick.
bool IsNewBar()
  {
   datetime currentBarTime = iTime(_Symbol, PERIOD_CURRENT, 0);
   if(lastBarTime == currentBarTime)
      return false;
   lastBarTime = currentBarTime;
   return true;
  }

// Loops over all open positions and pending orders; returns true if any belongs to
// this strategy (same symbol + magic number + comment).
// Used to enforce "one trade at a time": no new entry while our exposure exists.
bool HasStrategyExposure()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == Magic && PositionGetString(POSITION_COMMENT) == StrategyComment)
         return true;
     }
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong ticket = OrderGetTicket(i);
      if(ticket > 0 && OrderGetString(ORDER_SYMBOL) == _Symbol && OrderGetInteger(ORDER_MAGIC) == Magic && OrderGetString(ORDER_COMMENT) == StrategyComment)
         return true;
     }
   return false;
  }

// Closes every strategy position and deletes every strategy pending order.
void CloseStrategyPositionsAndOrders()
  {
   CloseStrategyPositions();
   DeleteStrategyOrders();
  }

// Closes each open position carrying this EA's magic number and comment,
// so positions opened manually or by other EAs are never touched.
void CloseStrategyPositions()
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong ticket = PositionGetTicket(i);
      if(ticket > 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == Magic && PositionGetString(POSITION_COMMENT) == StrategyComment)
         trade.PositionClose(ticket);
     }
  }

// Deletes each pending order carrying this EA's magic number and comment.
void DeleteStrategyOrders()
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong ticket = OrderGetTicket(i);
      if(ticket > 0 && OrderGetString(ORDER_SYMBOL) == _Symbol && OrderGetInteger(ORDER_MAGIC) == Magic && OrderGetString(ORDER_COMMENT) == StrategyComment)
         trade.OrderDelete(ticket);
     }
  }

// Opens a market BUY at the current ask.
// The stop-loss sits stopLossPercent below the entry; lot size is sized so that
// hitting the SL costs at most riskPercent of the account balance.
void ExecuteBuyMarket(double riskPercent, double stopLossPercent, string comment)
  {
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   double stopLossFraction = stopLossPercent / 100.0;
   double riskFraction = riskPercent / 100.0;
   // For a buy, the stop-loss is placed below the entry price.
   double sl = ask * (1.0 - stopLossFraction);
   double lots = CalculateLotsByRisk(ask - sl, riskFraction);
   if(lots <= 0.0)
      return;
   trade.Buy(lots, _Symbol, ask, sl, 0.0, comment);
  }

// Opens a market SELL at the current bid.
// The stop-loss sits stopLossPercent above the entry; lot size follows the same risk rule.
void ExecuteSellMarket(double riskPercent, double stopLossPercent, string comment)
  {
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double stopLossFraction = stopLossPercent / 100.0;
   double riskFraction = riskPercent / 100.0;
   // For a sell, the stop-loss is placed above the entry price.
   double sl = bid * (1.0 + stopLossFraction);
   double lots = CalculateLotsByRisk(sl - bid, riskFraction);
   if(lots <= 0.0)
      return;
   trade.Sell(lots, _Symbol, bid, sl, 0.0, comment);
  }

// Converts a money risk amount into a lot size.
// One lot step costs (SL distance / tick size) * tick value, so the lot count is
// floor(risk amount / cost per lot step), rounded down and clamped to broker limits.
double CalculateLotsByRisk(double stopLossDistance, double riskFraction)
  {
   if(stopLossDistance <= 0.0 || riskFraction <= 0.0)
      return 0.0;
   // Money we are willing to lose on this trade.
   double riskAmount = AccountInfoDouble(ACCOUNT_BALANCE) * riskFraction;
   double tickSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   double tickValue = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_VALUE);
   double lotStep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   double minLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   if(tickSize <= 0.0 || tickValue <= 0.0 || lotStep <= 0.0)
      return 0.0;
   // Money lost per one lot step if the stop-loss is hit.
   double moneyPerLotStep = stopLossDistance / tickSize * tickValue * lotStep;
   if(moneyPerLotStep <= 0.0)
      return 0.0;
   double lots = MathFloor(riskAmount / moneyPerLotStep) * lotStep;
   lots = MathMin(lots, maxLot);
   lots = MathMax(lots, minLot);
   return lots;
  }

// Current broker server time as minutes since midnight (e.g. 13:30 -> 810).
int CurrentServerMinutes()
  {
   datetime currentTime = TimeTradeServer();
   MqlDateTime timeStruct;
   TimeToStruct(currentTime, timeStruct);
   return timeStruct.hour * 60 + timeStruct.min;
  }

// True if the server time is inside the [start, end] window.
// The last branch handles windows that wrap past midnight (e.g. 22:00 - 02:00).
bool IsServerTimeInWindow(int startHour, int startMinute, int endHour, int endMinute)
  {
   int currentMinutes = CurrentServerMinutes();
   int startMinutes = startHour * 60 + startMinute;
   int endMinutes = endHour * 60 + endMinute;
   if(startMinutes <= endMinutes)
      return currentMinutes >= startMinutes && currentMinutes <= endMinutes;
   return currentMinutes >= startMinutes || currentMinutes <= endMinutes;
  }

// Returns midnight (00:00:00) of the day containing the given datetime.
datetime ServerDayStart(datetime value)
  {
   MqlDateTime timeStruct;
   TimeToStruct(value, timeStruct);
   timeStruct.hour = 0;
   timeStruct.min = 0;
   timeStruct.sec = 0;
   return StructToTime(timeStruct);
  }

// Returns true exactly once per day: the first tick at/after hour:minute server time.
// lastExecution stores the previous fire time so it cannot trigger twice in one day.
bool ShouldRunDailySchedule(int hour, int minute, datetime &lastExecution)
  {
   datetime currentTime = TimeTradeServer();
   datetime targetTime = ServerDayStart(currentTime) + hour * 3600 + minute * 60;
   if(currentTime >= targetTime && lastExecution < targetTime)
     {
      lastExecution = currentTime;
      return true;
     }
   return false;
  }

// Called by the terminal for every trade event (order placed, filled, closed...).
// When one of OUR orders gets filled, delete our remaining pending orders.
void OnTradeTransaction(const MqlTradeTransaction& trans, const MqlTradeRequest& request, const MqlTradeResult& result)
  {
   if(trans.type != TRADE_TRANSACTION_DEAL_ADD)
      return;
   if(trans.order == 0)
      return;
   if(HistoryOrderGetInteger(trans.order, ORDER_MAGIC) != Magic)
      return;
   if(HistoryOrderGetString(trans.order, ORDER_COMMENT) != StrategyComment)
      return;
   DeleteStrategyOrders();
  }

// Extra entry filter hook - currently accepts every signal.
// Add your own conditions here and return false to block an entry.
bool PassesFilters(SignalDirection signal)
  {
   return true;
  }

// Reads the EMAs of the last two CLOSED bars (shifts 1 and 2), so the signal never repaints.
// BUY: fast EMA crosses ABOVE slow EMA and the close is above the fast EMA and the 200 EMA.
// SELL: the mirror image. Anything else returns SIGNAL_NONE.
SignalDirection GetBackboneSignal()
  {
   double fastCurr[1], fastPrev[1], slowCurr[1], slowPrev[1], trendCurr[1];
   // shift 1 = last closed bar, shift 2 = the bar before it
   CopyBuffer(handleFastEma, 0, 1, 1, fastCurr);
   CopyBuffer(handleFastEma, 0, 2, 1, fastPrev);
   CopyBuffer(handleSlowEma, 0, 1, 1, slowCurr);
   CopyBuffer(handleSlowEma, 0, 2, 1, slowPrev);
   CopyBuffer(handleTrendEma, 0, 1, 1, trendCurr);
   double closeCurr = iClose(_Symbol, PERIOD_CURRENT, 1);

   // Bullish cross on the last closed bar + uptrend filter.
   if(fastPrev[0] <= slowPrev[0] && fastCurr[0] > slowCurr[0] && closeCurr > fastCurr[0] && closeCurr > trendCurr[0])
      return SIGNAL_BUY;
   // Bearish cross on the last closed bar + downtrend filter.
   if(fastPrev[0] >= slowPrev[0] && fastCurr[0] < slowCurr[0] && closeCurr < fastCurr[0] && closeCurr < trendCurr[0])
      return SIGNAL_SELL;

   return SIGNAL_NONE;
  }

// Main EA loop: runs on every tick, but the strategy logic executes only once per new bar.
// Order of checks: daily exit -> entry time window -> existing exposure -> signal.
void OnTick()
  {
   // Act only on the first tick of a new bar.
   if(!IsNewBar())
      return;

   // Once per day at ExitHour:ExitMinute, close everything and stop for the day.
   if(ShouldRunDailySchedule(ExitHour, ExitMinute, lastExitExecution))
     {
      CloseStrategyPositionsAndOrders();
      return;
     }

   // Outside the allowed entry window, do nothing.
   if(!IsServerTimeInWindow(EntryStartHour, EntryStartMinute, EntryEndHour, EntryEndMinute))
      return;

   // One trade at a time: skip if this strategy already has a position or pending order.
   if(HasStrategyExposure())
      return;

   SignalDirection signal = GetBackboneSignal();
   if(signal == SIGNAL_NONE)
      return;

   if(!PassesFilters(signal))
      return;

   // Open the trade in the direction of the signal.
   if(signal == SIGNAL_BUY)
      ExecuteBuyMarket(RiskPercent, StopLossPercent, StrategyComment);
   else if(signal == SIGNAL_SELL)
      ExecuteSellMarket(RiskPercent, StopLossPercent, StrategyComment);
  }