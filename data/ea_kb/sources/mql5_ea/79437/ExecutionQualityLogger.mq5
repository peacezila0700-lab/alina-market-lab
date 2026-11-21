//+------------------------------------------------------------------+
//|                                       ExecutionQualityLogger.mq5 |
//|  Measures the execution quality of your broker: for every deal   |
//|  on the account (manual, any EA, SL/TP hits) it records the       |
//|  requested price, the fill price, the slippage in points (+ =     |
//|  in your favour, - = against you), the delay from order to fill   |
//|  and the spread at that moment. Writes one CSV row per deal and   |
//|  shows a running summary on the chart. It never trades.           |
//+------------------------------------------------------------------+
#property copyright "Augusto Martin D'anna"
#property version   "1.00"
#property description "Logs slippage, fill delay and spread of every deal on the account to a CSV file and shows a live summary."
#property description "Works with manual trades, other EAs and SL/TP executions. It does not open or modify trades."

input string InpFileName  = "execution_quality.csv"; // CSV file (MQL5\Files or Common\Files)
input bool   InpCommon    = false;                   // Use the Common\Files folder
input string InpSymbol    = "";                      // Only this symbol ("" = all)
input long   InpMagic     = -1;                      // Only this magic (-1 = all, 0 = manual)
input bool   InpShowPanel = true;                    // Show the summary on the chart

struct SStats
  {
   int               deals;
   int               measured;
   int               negative;
   double            sumSlip;
   double            worstSlip;
   double            sumDelay;
   double            maxDelay;
  };

SStats g_stats;
int    g_file = INVALID_HANDLE;

//+------------------------------------------------------------------+
//| Open the CSV in append mode and write the header once            |
//+------------------------------------------------------------------+
bool OpenFile()
  {
   int flags = FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ | (InpCommon ? FILE_COMMON : 0);
   g_file = FileOpen(InpFileName, flags, ',');
   if(g_file == INVALID_HANDLE)
     {
      PrintFormat("EQL: cannot open %s, error %d", InpFileName, GetLastError());
      return false;
     }
   if(FileSize(g_file) == 0)
      FileWrite(g_file, "deal_time", "symbol", "deal", "order", "magic", "reason", "entry", "side", "volume",
                "requested", "filled", "slippage_points", "delay_ms", "spread_points");
   FileSeek(g_file, 0, SEEK_END);
   return true;
  }

string ReasonText(const long reason)
  {
   switch((int)reason)
     {
      case DEAL_REASON_SL:     return "SL";
      case DEAL_REASON_TP:     return "TP";
      case DEAL_REASON_SO:     return "stop_out";
      case DEAL_REASON_EXPERT: return "expert";
      case DEAL_REASON_CLIENT: return "manual";
      case DEAL_REASON_MOBILE: return "mobile";
      case DEAL_REASON_WEB:    return "web";
      default:                 return "other";
     }
  }

//+------------------------------------------------------------------+
//| Requested price of the order that produced the deal              |
//| market orders: price when sent; SL/TP: the stop/target level     |
//+------------------------------------------------------------------+
// HistoryOrderSelect/HistoryDealSelect would reset the HistorySelect() list, so tickets are read from that list
bool InHistory(const ulong order) { return order > 0 && (ulong)HistoryOrderGetInteger(order, ORDER_TICKET) == order; }

//--- quote at the moment the order was placed: used when the server stores no price for market orders
double QuoteAt(const string symbol, const long msc, const bool buy)
  {
   MqlTick t[];
   int n = CopyTicks(symbol, t, COPY_TICKS_INFO, (ulong)MathMax(msc - 60000, 0), 2000);
   double q = 0;
   for(int i = 0; i < n && t[i].time_msc <= msc; i++)
      q = buy ? t[i].ask : t[i].bid;
   return q;
  }

double RequestedPrice(const ulong order, const long reason)
  {
   if(!InHistory(order))
      return 0;
   if(reason == DEAL_REASON_SL && HistoryOrderGetDouble(order, ORDER_SL) > 0)
      return HistoryOrderGetDouble(order, ORDER_SL);
   if(reason == DEAL_REASON_TP && HistoryOrderGetDouble(order, ORDER_TP) > 0)
      return HistoryOrderGetDouble(order, ORDER_TP);
   double p = HistoryOrderGetDouble(order, ORDER_PRICE_OPEN);
   if(p > 0)
      return p;
   long type = HistoryOrderGetInteger(order, ORDER_TYPE);
   return QuoteAt(HistoryOrderGetString(order, ORDER_SYMBOL), HistoryOrderGetInteger(order, ORDER_TIME_SETUP_MSC), type == ORDER_TYPE_BUY);
  }
//+------------------------------------------------------------------+
//| Record one deal                                                  |
//+------------------------------------------------------------------+
void LogDeal(const ulong deal)
  {
   if((ulong)HistoryDealGetInteger(deal, DEAL_TICKET) != deal)
      return;
   long type = HistoryDealGetInteger(deal, DEAL_TYPE);
   if(type != DEAL_TYPE_BUY && type != DEAL_TYPE_SELL)
      return;                                           // balance operations, commissions...
   string symbol = HistoryDealGetString(deal, DEAL_SYMBOL);
   long magic = HistoryDealGetInteger(deal, DEAL_MAGIC);
   if((InpSymbol != "" && symbol != InpSymbol) || (InpMagic >= 0 && magic != InpMagic))
      return;
   ulong order = (ulong)HistoryDealGetInteger(deal, DEAL_ORDER);
   long reason = HistoryDealGetInteger(deal, DEAL_REASON);
   double filled = HistoryDealGetDouble(deal, DEAL_PRICE);
   double requested = RequestedPrice(order, reason);
   double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
   int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   bool buy = (type == DEAL_TYPE_BUY);
   //--- buying lower / selling higher than requested is in your favour
   double slip = (requested > 0 && point > 0) ? (buy ? requested - filled : filled - requested) / point : 0;
   long delay = 0;
   if(InHistory(order))
      delay = HistoryDealGetInteger(deal, DEAL_TIME_MSC) - HistoryOrderGetInteger(order, ORDER_TIME_SETUP_MSC);
   MqlTick tick;
   double spread = SymbolInfoTick(symbol, tick) && point > 0 ? (tick.ask - tick.bid) / point : 0;
   long entry = HistoryDealGetInteger(deal, DEAL_ENTRY);

   if(g_file != INVALID_HANDLE)
     {
      FileWrite(g_file, TimeToString((datetime)HistoryDealGetInteger(deal, DEAL_TIME), TIME_DATE | TIME_SECONDS), symbol,
                (string)deal, (string)order, (string)magic, ReasonText(reason),
                entry == DEAL_ENTRY_IN ? "in" : entry == DEAL_ENTRY_OUT ? "out" : "inout", buy ? "buy" : "sell",
                DoubleToString(HistoryDealGetDouble(deal, DEAL_VOLUME), 2), DoubleToString(requested, digits),
                DoubleToString(filled, digits), DoubleToString(slip, 1), (string)delay, DoubleToString(spread, 1));
      FileFlush(g_file);
     }
   g_stats.deals++;
   if(requested > 0)
     {
      g_stats.measured++;
      g_stats.sumSlip += slip;
      if(slip < 0)
         g_stats.negative++;
      g_stats.worstSlip = MathMin(g_stats.worstSlip, slip);
      g_stats.sumDelay += (double)delay;
      g_stats.maxDelay = MathMax(g_stats.maxDelay, (double)delay);
     }
   ShowPanel();
  }

void ShowPanel()
  {
   if(!InpShowPanel)
      return;
   int n = MathMax(g_stats.measured, 1);
   Comment(StringFormat("ExecutionQualityLogger\nDeals logged: %d (measured %d)\nAvg slippage: %.1f pts   worst: %.1f pts\n"
                        "Negative slippage: %d (%.0f%%)\nAvg delay: %.0f ms   max: %.0f ms",
                        g_stats.deals, g_stats.measured, g_stats.sumSlip / n, g_stats.worstSlip, g_stats.negative,
                        100.0 * g_stats.negative / n, g_stats.sumDelay / n, g_stats.maxDelay));
  }

//+------------------------------------------------------------------+
//| Every new deal on the account arrives here                       |
//+------------------------------------------------------------------+
//| The order that produced a deal reaches the history a moment      |
//| after the deal, so deals wait in a queue until it is there.      |
//+------------------------------------------------------------------+
ulong    g_queue[];
datetime g_queued[];

void ProcessQueue()
  {
   int n = ArraySize(g_queue);
   if(n == 0)
      return;
   HistorySelect(TimeCurrent() - 86400, TimeCurrent() + 86400);
   for(int i = n - 1; i >= 0; i--)
     {
      ulong order = (ulong)HistoryDealGetInteger(g_queue[i], DEAL_ORDER);
      bool ready = InHistory(order) && RequestedPrice(order, HistoryDealGetInteger(g_queue[i], DEAL_REASON)) > 0;
      if(!ready && TimeLocal() - g_queued[i] < 10)
         continue;                                      // order not in the history yet: try again later
      LogDeal(g_queue[i]);                              // after 10 s it is logged without the requested price
      ArrayRemove(g_queue, i, 1);
      ArrayRemove(g_queued, i, 1);
     }
  }

void OnTimer() { ProcessQueue(); }

void OnTradeTransaction(const MqlTradeTransaction &trans, const MqlTradeRequest &request, const MqlTradeResult &result)
  {
   if(trans.type == TRADE_TRANSACTION_DEAL_ADD && trans.deal > 0)
     {
      int n = ArraySize(g_queue);
      ArrayResize(g_queue, n + 1);
      ArrayResize(g_queued, n + 1);
      g_queue[n] = trans.deal;
      g_queued[n] = TimeLocal();
     }
   if(trans.type == TRADE_TRANSACTION_HISTORY_ADD)
      ProcessQueue();
   //--- rejected requests sent by this terminal's programs are reported in the Experts log
   if(trans.type == TRADE_TRANSACTION_REQUEST && result.retcode != TRADE_RETCODE_DONE && result.retcode != TRADE_RETCODE_PLACED
      && result.retcode != TRADE_RETCODE_DONE_PARTIAL)
      PrintFormat("EQL: request rejected or requoted, retcode %u (%s)", result.retcode, result.comment);
  }

int OnInit()
  {
   ZeroMemory(g_stats);
   if(!OpenFile())
      return INIT_FAILED;
   ShowPanel();
   EventSetMillisecondTimer(500);
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   EventKillTimer();
   ProcessQueue();
   if(g_file != INVALID_HANDLE)
      FileClose(g_file);
   Comment("");
  }
//+------------------------------------------------------------------+
