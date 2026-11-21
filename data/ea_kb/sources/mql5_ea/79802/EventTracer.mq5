//+------------------------------------------------------------------+
//|                                                  EventTracer.mq5 |
//| Shows when which event handler of an Expert Advisor runs.        |
//+------------------------------------------------------------------+
#property version     "1.00"
#property description "Teaching and diagnosis tool: prints one line to the Experts journal each time"
#property description "an event handler runs (OnInit, OnDeinit, OnTick, OnTimer, OnTrade, OnTradeTransaction,"
#property description "OnBookEvent, OnChartEvent, OnTester, OnTesterInit, OnTesterPass, OnTesterDeinit),"
#property description "with a running number, local and server time and the test mode."
#property description "Shows what survives a change of symbol, timeframe or inputs, and what a Strategy Tester"
#property description "pass or optimization runs where. It never trades: no orders, no signals, no alerts."

//--- the handlers that are traced, one counter each
enum ENUM_TRACED_EVENT
  {
   EVENT_INIT = 0,
   EVENT_DEINIT,
   EVENT_TICK,
   EVENT_TIMER,
   EVENT_TRADE,
   EVENT_TRADE_TRANSACTION,
   EVENT_BOOK,
   EVENT_CHART,
   EVENT_TESTER,
   EVENT_TESTER_INIT,
   EVENT_TESTER_PASS,
   EVENT_TESTER_DEINIT,
   EVENT_TOTAL
  };

//+------------------------------------------------------------------+
//| Inputs                                                           |
//+------------------------------------------------------------------+
input int  InpTimerSeconds = 60;     // Timer period in seconds (0 to 86400, 0 = no timer)
input bool InpLogEveryTick = false;  // Print every tick and book event (false: first one per second)
input bool InpSubscribeBook = false; // Subscribe to the Depth of Market of the chart symbol
input int  InpTesterLines = 20;      // Strategy Tester: printed lines per handler (0 = no limit)

#define ET_MAX_TIMER_SECONDS 86400         // upper limit for InpTimerSeconds (one day)
#define ET_FRAME_NAME        "EventTracer" // name of the frame that carries the counts of one pass
#define ET_FRAME_ID          1             // id of that frame
#define ET_NUMBER_DIGITS     6             // digits of the running number in a line
#define ET_PERIOD_PREFIX     "PERIOD_"     // prefix that EnumToString puts before a timeframe

//--- program-level state: survives a change of symbol, timeframe or inputs
ulong    g_event_number = 0;          // running number of the handler calls, never reset
long     g_counts[EVENT_TOTAL];       // calls per handler since the program was loaded, never reset

//--- per-run state: reset in OnInit
long     g_printed[EVENT_TOTAL];      // lines printed per handler (for the Strategy Tester limit)
bool     g_limit_noted[EVENT_TOTAL];  // the "further calls are not printed" line was printed
datetime g_last_second[EVENT_TOTAL];  // server second of the last printed tick or book event
string   g_book_symbol = "";          // symbol whose Depth of Market is subscribed, "" if none

//--- state of the copy that receives the frames of an optimization
long     g_frames_received = 0;       // frames of this program read by OnTesterPass and OnTesterDeinit
long     g_frames_printed = 0;        // frames printed
bool     g_frame_limit_noted = false; // the "further frames are not printed" line was printed
long     g_frame_totals[EVENT_TOTAL]; // calls per handler, added up over all frames

//+------------------------------------------------------------------+
//| Expert initialization function                                   |
//+------------------------------------------------------------------+
int OnInit()
  {
//--- only the per-run state is reset, the counters go on
   ResetRunState();
   CountEvent(EVENT_INIT);
   if(ShouldPrint(EVENT_INIT))
      PrintEvent(EVENT_INIT, InitDetails());

//--- a wrong input ends the program; OnDeinit then runs with REASON_INITFAILED
   if(!InputsAreValid())
      return INIT_PARAMETERS_INCORRECT;

   StartTimerAndBook();
   return INIT_SUCCEEDED;
  }

//+------------------------------------------------------------------+
//| Expert deinitialization function                                 |
//+------------------------------------------------------------------+
void OnDeinit(const int reason)
  {
   CountEvent(EVENT_DEINIT);
   const bool print = ShouldPrint(EVENT_DEINIT);
   if(print)
      PrintEvent(EVENT_DEINIT, StringFormat("reason %d, %s", reason, ReasonText(reason)));

//--- stop the timer and release the Depth of Market that OnInit subscribed
   EventKillTimer();
   if(g_book_symbol != "")
     {
      MarketBookRelease(g_book_symbol);
      g_book_symbol = "";
     }
//--- in the Strategy Tester the OnTester line already holds these counts
   if(print && MQLInfoInteger(MQL_TESTER) == 0)
      Print("Event Tracer summary, calls per handler since the program was loaded: ", CountsText(g_counts));
  }

//+------------------------------------------------------------------+
//| Expert tick function                                             |
//+------------------------------------------------------------------+
void OnTick()
  {
   CountEvent(EVENT_TICK);
   if(!ShouldPrint(EVENT_TICK))
      return;

//--- the details are only read when the line is printed
   MqlTick tick;
   ResetLastError();
   if(!SymbolInfoTick(_Symbol, tick))
     {
      PrintEvent(EVENT_TICK, StringFormat("SymbolInfoTick failed, error %d", GetLastError()));
      return;
     }
   PrintEvent(EVENT_TICK, StringFormat("bid=%s ask=%s", DoubleToString(tick.bid, _Digits),
                                       DoubleToString(tick.ask, _Digits)));
  }

//+------------------------------------------------------------------+
//| Timer function                                                   |
//+------------------------------------------------------------------+
void OnTimer()
  {
   CountEvent(EVENT_TIMER);
   if(ShouldPrint(EVENT_TIMER))
      PrintEvent(EVENT_TIMER, StringFormat("timer period %d s", InpTimerSeconds));
  }

//+------------------------------------------------------------------+
//| Trade function                                                   |
//+------------------------------------------------------------------+
void OnTrade()
  {
   CountEvent(EVENT_TRADE);
   if(ShouldPrint(EVENT_TRADE))
      PrintEvent(EVENT_TRADE, "");
  }

//+------------------------------------------------------------------+
//| Trade transaction function: only reads the transaction           |
//+------------------------------------------------------------------+
void OnTradeTransaction(const MqlTradeTransaction &trans,
                        const MqlTradeRequest &request,
                        const MqlTradeResult &result)
  {
   CountEvent(EVENT_TRADE_TRANSACTION);
   if(!ShouldPrint(EVENT_TRADE_TRANSACTION))
      return;

//--- a request transaction leaves trans empty: its data is in request and result
   if(trans.type == TRADE_TRANSACTION_REQUEST)
     {
      PrintEvent(EVENT_TRADE_TRANSACTION,
                 StringFormat("%s symbol=%s order=%I64u deal=%I64u position=%I64u retcode=%u",
                              EnumToString(trans.type), request.symbol, result.order, result.deal,
                              request.position, result.retcode));
      return;
     }
   PrintEvent(EVENT_TRADE_TRANSACTION,
              StringFormat("%s symbol=%s order=%I64u deal=%I64u position=%I64u",
                           EnumToString(trans.type), trans.symbol, trans.order, trans.deal, trans.position));
  }

//+------------------------------------------------------------------+
//| Depth of Market event function                                   |
//+------------------------------------------------------------------+
void OnBookEvent(const string &symbol)
  {
   CountEvent(EVENT_BOOK);
   if(ShouldPrint(EVENT_BOOK))
      PrintEvent(EVENT_BOOK, "symbol=" + symbol);
  }

//+------------------------------------------------------------------+
//| Chart event function                                             |
//+------------------------------------------------------------------+
void OnChartEvent(const int id, const long &lparam, const double &dparam, const string &sparam)
  {
   CountEvent(EVENT_CHART);
   if(ShouldPrint(EVENT_CHART))
      PrintEvent(EVENT_CHART, StringFormat("%s lparam=%I64d dparam=%g sparam=%s",
                                           ChartEventName(id), lparam, dparam, sparam));
  }

//+------------------------------------------------------------------+
//| Tester function: runs once at the end of a Strategy Tester pass. |
//| The returned custom criterion is the number of events, not a     |
//| trading result. The counts go to the terminal in a frame.        |
//+------------------------------------------------------------------+
double OnTester()
  {
   CountEvent(EVENT_TESTER);
   if(ShouldPrint(EVENT_TESTER))
      PrintEvent(EVENT_TESTER, "calls in this test run: " + CountsText(g_counts) +
                 " | the custom criterion is the number of events, not a trading result");

//--- in an optimization FrameAdd sends the counts to the terminal, where OnTesterPass receives them
   ResetLastError();
   if(MQLInfoInteger(MQL_OPTIMIZATION) != 0 &&
      !FrameAdd(ET_FRAME_NAME, ET_FRAME_ID, (double)g_event_number, g_counts))
      PrintFormat("Event Tracer: FrameAdd failed, error %d", GetLastError());
   return (double)g_event_number;
  }

//+------------------------------------------------------------------+
//| Runs once in the terminal before an optimization starts          |
//+------------------------------------------------------------------+
void OnTesterInit()
  {
   CountEvent(EVENT_TESTER_INIT);
   if(ShouldPrint(EVENT_TESTER_INIT))
      PrintEvent(EVENT_TESTER_INIT, "this instance runs on a chart in the terminal in frame mode, not on a test agent");
  }

//+------------------------------------------------------------------+
//| Runs in the terminal each time a pass has sent frames            |
//+------------------------------------------------------------------+
void OnTesterPass()
  {
   CountEvent(EVENT_TESTER_PASS);
   ProcessFrames(EVENT_TESTER_PASS);
  }

//+------------------------------------------------------------------+
//| Runs once in the terminal after the optimization has finished    |
//+------------------------------------------------------------------+
void OnTesterDeinit()
  {
   CountEvent(EVENT_TESTER_DEINIT);
   if(ShouldPrint(EVENT_TESTER_DEINIT))
      PrintEvent(EVENT_TESTER_DEINIT, "frames not yet read by OnTesterPass are read now");
   ProcessFrames(EVENT_TESTER_DEINIT);
   PrintFormat("Event Tracer summary: %I64d frame(s) received, %I64d printed; calls per handler over all passes: %s",
               g_frames_received, g_frames_printed, CountsText(g_frame_totals));
  }

//+------------------------------------------------------------------+
//| Resets what belongs to one run. OnInit runs again after a change |
//| of symbol, timeframe or inputs, but the program stays loaded, so |
//| its global variables keep their values. That is why only the     |
//| per-run state is reset here. g_event_number and the call         |
//| counters are not reset on purpose: they show what survives such  |
//| a change. The frame state is not reset either: the copy that     |
//| receives the frames is loaded for one optimization and does not  |
//| run OnInit, so it relies on the zero values of a fresh load.     |
//+------------------------------------------------------------------+
void ResetRunState()
  {
   ArrayInitialize(g_printed, 0);
   ArrayInitialize(g_limit_noted, false);
   ArrayInitialize(g_last_second, 0);
   g_book_symbol = "";
  }

//+------------------------------------------------------------------+
//| Gives the call its number and counts it. Done for every call,    |
//| printed or not, so gaps in the numbers show the throttling.      |
//+------------------------------------------------------------------+
void CountEvent(const ENUM_TRACED_EVENT event)
  {
   g_event_number++;
   g_counts[event]++;
  }

//+------------------------------------------------------------------+
//| Decides whether this call prints a line. The rules:              |
//| 1. On a test agent during an optimization nothing is printed     |
//|    (the terminal does not show the journal of the agents then);  |
//|    the counts travel to the terminal in a frame.                 |
//| 2. OnInit, OnDeinit, OnTester, OnTesterInit and OnTesterDeinit   |
//|    are always printed.                                           |
//| 3. OnTick and OnBookEvent print only the first call per server   |
//|    second, unless InpLogEveryTick is set. The second is kept per |
//|    handler, not per symbol: book events of several symbols share |
//|    it.                                                           |
//| 4. In the Strategy Tester the handlers listed in                 |
//|    IsTesterLimited print at most InpTesterLines lines each.      |
//| Updates the throttle state when it returns true, and prints the  |
//| note about the limit once when rule 4 holds a line back.         |
//| OnTesterPass does not come here: its lines are limited per frame |
//| in PrintFrame.                                                   |
//+------------------------------------------------------------------+
bool ShouldPrint(const ENUM_TRACED_EVENT event)
  {
//--- rule 1: a test agent during an optimization stays silent
   if(MQLInfoInteger(MQL_OPTIMIZATION) != 0 && MQLInfoInteger(MQL_FRAME_MODE) == 0)
      return false;
//--- rule 2: these handlers are always printed
   if(IsAlwaysPrinted(event))
      return true;
//--- rule 3: tick and book events, first one per server second
   const bool     perSecond = (event == EVENT_TICK || event == EVENT_BOOK) && !InpLogEveryTick;
   const datetime second = perSecond ? TimeTradeServer() : 0;
   if(perSecond && second == g_last_second[event])
      return false;
//--- rule 4: Strategy Tester line limit per handler, 0 means no limit
   if(MQLInfoInteger(MQL_TESTER) != 0 && InpTesterLines > 0 && IsTesterLimited(event) &&
      g_printed[event] >= InpTesterLines)
     {
      NoteLimit(event);
      return false;
     }
   g_last_second[event] = second;
   g_printed[event]++;
   return true;
  }

//+------------------------------------------------------------------+
//| True for the handlers that are never throttled.                  |
//+------------------------------------------------------------------+
bool IsAlwaysPrinted(const ENUM_TRACED_EVENT event)
  {
   return event == EVENT_INIT || event == EVENT_DEINIT || event == EVENT_TESTER ||
          event == EVENT_TESTER_INIT || event == EVENT_TESTER_DEINIT;
  }

//+------------------------------------------------------------------+
//| True for the handlers that the Strategy Tester line limit        |
//| applies to.                                                      |
//+------------------------------------------------------------------+
bool IsTesterLimited(const ENUM_TRACED_EVENT event)
  {
   return event == EVENT_TICK || event == EVENT_TIMER || event == EVENT_TRADE ||
          event == EVENT_TRADE_TRANSACTION || event == EVENT_BOOK || event == EVENT_CHART;
  }

//+------------------------------------------------------------------+
//| Prints once per handler that the line limit has been reached.    |
//+------------------------------------------------------------------+
void NoteLimit(const ENUM_TRACED_EVENT event)
  {
   if(g_limit_noted[event])
      return;
   g_limit_noted[event] = true;
   PrintFormat("... further %s calls are counted but not printed (limit %d)", EventName(event), InpTesterLines);
  }

//+------------------------------------------------------------------+
//| Reads the frames that are waiting and prints them. The first     |
//| InpTesterLines frames are printed (0 = no limit), all are        |
//| counted and added to the totals. Frames of other programs are    |
//| skipped.                                                         |
//+------------------------------------------------------------------+
void ProcessFrames(const ENUM_TRACED_EVENT event)
  {
   ulong  pass;
   string name;
   long   id;
   double value;
   long   counts[];
//--- read every frame that is waiting; FrameNext moves on by itself
   while(FrameNext(pass, name, id, value, counts))
     {
      //--- frames of other programs and frames of another layout are left out
      if(name != ET_FRAME_NAME || id != ET_FRAME_ID)
         continue;
      if(ArraySize(counts) != EVENT_TOTAL)
        {
         PrintFormat("Event Tracer: frame of pass %I64u skipped, it holds %d counts instead of %d",
                     pass, ArraySize(counts), EVENT_TOTAL);
         continue;
        }
      //--- count the frame, add it to the totals and print it
      g_frames_received++;
      for(int i = 0; i < EVENT_TOTAL; i++)
         g_frame_totals[i] += counts[i];
      PrintFrame(event, pass, value, counts);
     }
  }

//+------------------------------------------------------------------+
//| Prints one frame, within the InpTesterLines limit.               |
//+------------------------------------------------------------------+
void PrintFrame(const ENUM_TRACED_EVENT event, const ulong pass, const double value, const long &counts[])
  {
//--- over the limit: say so once, then stay silent
   if(InpTesterLines > 0 && g_frames_printed >= InpTesterLines)
     {
      if(!g_frame_limit_noted)
        {
         g_frame_limit_noted = true;
         PrintFormat("... further frames are counted but not printed (limit %d)", InpTesterLines);
        }
      return;
     }
   g_frames_printed++;
   PrintEvent(event, StringFormat("pass %I64u | total events %.0f | %s", pass, value, CountsText(counts)));
  }

//+------------------------------------------------------------------+
//| Checks the inputs; prints the reason when one is invalid.        |
//+------------------------------------------------------------------+
bool InputsAreValid()
  {
   if(InpTimerSeconds < 0 || InpTimerSeconds > ET_MAX_TIMER_SECONDS)
     {
      PrintFormat("Event Tracer: \"Timer period in seconds\" must be between 0 and %d, it is %d.",
                  ET_MAX_TIMER_SECONDS, InpTimerSeconds);
      return false;
     }
   if(InpTesterLines < 0)
     {
      PrintFormat("Event Tracer: \"Strategy Tester: printed lines per handler\" must be 0 or more, it is %d.",
                  InpTesterLines);
      return false;
     }
   return true;
  }

//+------------------------------------------------------------------+
//| Starts the timer and subscribes to the Depth of Market if the    |
//| inputs ask for it. A failure is reported, the program goes on.   |
//+------------------------------------------------------------------+
void StartTimerAndBook()
  {
//--- timer
   if(InpTimerSeconds > 0)
     {
      ResetLastError();
      if(!EventSetTimer(InpTimerSeconds))
         PrintFormat("Event Tracer: EventSetTimer(%d) failed, error %d, OnTimer will not run",
                     InpTimerSeconds, GetLastError());
     }
//--- Depth of Market; the symbol is remembered so that OnDeinit releases this one
//--- even if the chart has moved to another symbol by then
   if(InpSubscribeBook)
     {
      ResetLastError();
      if(MarketBookAdd(_Symbol))
         g_book_symbol = _Symbol;
      else
         PrintFormat("Event Tracer: MarketBookAdd(%s) failed, error %d, OnBookEvent will not run",
                     _Symbol, GetLastError());
     }
  }

//+------------------------------------------------------------------+
//| Details of the OnInit line: symbol, timeframe, the init counter  |
//| and why the program was deinitialized before. A freshly loaded   |
//| program reports reason 0. That is also what a run after a        |
//| recompile showed: the program is loaded again, the numbering     |
//| starts at 1 and UninitializeReason returns 0. Any other reason   |
//| on the first call is printed as it is reported.                  |
//+------------------------------------------------------------------+
string InitDetails()
  {
   const int    reason = UninitializeReason();
   const string previous = (g_counts[EVENT_INIT] == 1 && reason == REASON_PROGRAM)
                           ? "none, the program was just loaded" : ReasonText(reason);
   return StringFormat("%s %s | init call %I64d since the program was loaded | previous deinit reason: %s",
                       _Symbol, TimeframeName(_Period), g_counts[EVENT_INIT], previous);
  }

//+------------------------------------------------------------------+
//| Prints one line: number, handler, times, test mode and details.  |
//+------------------------------------------------------------------+
void PrintEvent(const ENUM_TRACED_EVENT event, const string details)
  {
//--- the head is the same for every handler, the details follow after a bar
   const string head = StringFormat("#%s %s | local %s | server %s | tester=%d visual=%d optimization=%d frame=%d",
                                    IntegerToString((long)g_event_number, ET_NUMBER_DIGITS, '0'), EventName(event),
                                    TimeToString(TimeLocal(), TIME_DATE | TIME_SECONDS),
                                    TimeToString(TimeTradeServer(), TIME_DATE | TIME_SECONDS),
                                    MQLInfoInteger(MQL_TESTER), MQLInfoInteger(MQL_VISUAL_MODE),
                                    MQLInfoInteger(MQL_OPTIMIZATION), MQLInfoInteger(MQL_FRAME_MODE));
   Print(details == "" ? head : head + " | " + details);
  }

//+------------------------------------------------------------------+
//| "OnInit=1 OnTick=120 ...": only handlers with a count above 0.   |
//+------------------------------------------------------------------+
string CountsText(const long &counts[])
  {
   string text = "";
   for(int i = 0; i < EVENT_TOTAL; i++)
     {
      if(counts[i] <= 0)
         continue;
      text += (text == "" ? "" : " ") + EventName((ENUM_TRACED_EVENT)i) + "=" + IntegerToString(counts[i]);
     }
   return text == "" ? "none" : text;
  }

//+------------------------------------------------------------------+
//| Name of a handler.                                               |
//+------------------------------------------------------------------+
string EventName(const ENUM_TRACED_EVENT event)
  {
   switch(event)
     {
      case EVENT_INIT:
         return "OnInit";
      case EVENT_DEINIT:
         return "OnDeinit";
      case EVENT_TICK:
         return "OnTick";
      case EVENT_TIMER:
         return "OnTimer";
      case EVENT_TRADE:
         return "OnTrade";
      case EVENT_TRADE_TRANSACTION:
         return "OnTradeTransaction";
      case EVENT_BOOK:
         return "OnBookEvent";
      case EVENT_CHART:
         return "OnChartEvent";
      case EVENT_TESTER:
         return "OnTester";
      case EVENT_TESTER_INIT:
         return "OnTesterInit";
      case EVENT_TESTER_PASS:
         return "OnTesterPass";
      case EVENT_TESTER_DEINIT:
         return "OnTesterDeinit";
      default:
         return "unknown handler";
     }
  }

//+------------------------------------------------------------------+
//| Plain-text explanation of a deinitialization reason code.        |
//+------------------------------------------------------------------+
string ReasonText(const int reason)
  {
   switch(reason)
     {
      case REASON_PROGRAM:
         return "REASON_PROGRAM: the program stopped itself with ExpertRemove";
      case REASON_REMOVE:
         return "REASON_REMOVE: the program was removed from the chart";
      case REASON_RECOMPILE:
         return "REASON_RECOMPILE: the program was recompiled";
      case REASON_CHARTCHANGE:
         return "REASON_CHARTCHANGE: symbol or timeframe of the chart was changed";
      case REASON_CHARTCLOSE:
         return "REASON_CHARTCLOSE: the chart was closed";
      case REASON_PARAMETERS:
         return "REASON_PARAMETERS: the input parameters were changed";
      case REASON_ACCOUNT:
         return "REASON_ACCOUNT: another account was activated or the terminal reconnected after account changes";
      case REASON_TEMPLATE:
         return "REASON_TEMPLATE: another chart template was applied";
      case REASON_INITFAILED:
         return "REASON_INITFAILED: OnInit returned a non-zero value";
      case REASON_CLOSE:
         return "REASON_CLOSE: the terminal was closed";
      default:
         return StringFormat("unknown reason %d", reason);
     }
  }

//+------------------------------------------------------------------+
//| Name of a chart event; custom events show as CHARTEVENT_CUSTOM+n.|
//+------------------------------------------------------------------+
string ChartEventName(const int id)
  {
   switch(id)
     {
      case CHARTEVENT_KEYDOWN:
         return "CHARTEVENT_KEYDOWN";
      case CHARTEVENT_MOUSE_MOVE:
         return "CHARTEVENT_MOUSE_MOVE";
      case CHARTEVENT_OBJECT_CREATE:
         return "CHARTEVENT_OBJECT_CREATE";
      case CHARTEVENT_OBJECT_CHANGE:
         return "CHARTEVENT_OBJECT_CHANGE";
      case CHARTEVENT_OBJECT_DELETE:
         return "CHARTEVENT_OBJECT_DELETE";
      case CHARTEVENT_CLICK:
         return "CHARTEVENT_CLICK";
      case CHARTEVENT_OBJECT_CLICK:
         return "CHARTEVENT_OBJECT_CLICK";
      case CHARTEVENT_OBJECT_DRAG:
         return "CHARTEVENT_OBJECT_DRAG";
      case CHARTEVENT_OBJECT_ENDEDIT:
         return "CHARTEVENT_OBJECT_ENDEDIT";
      case CHARTEVENT_CHART_CHANGE:
         return "CHARTEVENT_CHART_CHANGE";
      case CHARTEVENT_MOUSE_WHEEL:
         return "CHARTEVENT_MOUSE_WHEEL";
      default:
         return id >= CHARTEVENT_CUSTOM ? StringFormat("CHARTEVENT_CUSTOM+%d", id - CHARTEVENT_CUSTOM)
                : IntegerToString(id);
     }
  }

//+------------------------------------------------------------------+
//| PERIOD_H1 -> "H1": cuts the prefix that EnumToString adds.       |
//+------------------------------------------------------------------+
string TimeframeName(const ENUM_TIMEFRAMES period)
  {
   return StringSubstr(EnumToString(period), StringLen(ET_PERIOD_PREFIX));
  }
//+------------------------------------------------------------------+
