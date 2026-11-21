//+------------------------------------------------------------------+
//| GianoRangeBreakout.mq5 - session range breakout for XAUUSD        |
//|                                                                  |
//| Rule (all times are broker SERVER time):                         |
//|  1. Range = high/low of the M1 bars from 01:00 to 06:00. Valid   |
//|     only if at least 30 of the 60 five-minute slots have quotes. |
//|  2. Breakout = the first M15 bar (opened 06:15...21:30) that     |
//|     CLOSES above the high (BUY) or below the low (SELL).         |
//|     The first breakout decides the day: no second attempt.       |
//|  3. Entry at the first quote after that bar closes.              |
//|     SL = opposite side of the range; TP = one range size beyond  |
//|     the broken side. Skip if the price is already past the TP.   |
//|  4. Any open position is closed from 22:00.                      |
//|                                                                  |
//| Safety: every decision is written to a hash-chained journal      |
//| BEFORE the order is sent. After a restart the EA rebuilds its    |
//| state from journal, orders, positions and deals, and never sends |
//| a second entry for the same day. If the state cannot be rebuilt, |
//| it takes no new entry that day (exits are still managed).        |
//|                                                                  |
//| The rule lives in Include/GianoRangeBreakout/                    |
//| GianoRangeBreakout_Logic.mqh (pure functions, no broker calls,   |
//| covered by 59 offline checks).                                   |
//|                                                                  |
//| Research code. No edge is claimed. Test on a demo account first. |
//+------------------------------------------------------------------+
#property copyright "Giano"
#property version   "1.00"
#property description "Session range breakout (range 01:00-06:00 server time, M15 close breakout, exit at 22:00). Designed for XAUUSD."
#property description "Hash-chained journal written before every order; one decision per day, also after restarts."
#property description "Research code: no edge is claimed. Use a demo account first."

#include <Trade/Trade.mqh>
#include <GianoRangeBreakout/GianoRangeBreakout_Logic.mqh>

input double InpLots          = 0.01;       // Fixed volume (lots)
input long   InpMagic         = 20261029;   // Magic number
input bool   InpSaveExitTicks = false;      // Save BID/ASK ticks around each SL/TP exit (CSV files)

const string VERSION = "1.00";

CTrade   trade;
double   g_tick = 0.0;

// journal (one file per account, symbol and magic number, in MQL5/Files)
string   g_base = "";
string   g_journal = "";
string   g_hash = "GENESIS";
long     g_seq = 0;
string   g_ev[];                 // lines read at start: event
string   g_dy[];                 //   day
string   g_da[];                 //   data
bool     g_jr_expected = false;
bool     g_jr_present = false;
bool     g_jr_intact = true;
string   g_jr_problem = "";      // written as BLOCK on the first tick

// session
long     g_first_tick_msc = 0;
long     g_now_msc = 0;

// current day
datetime g_d0 = 0;
bool     g_decided = false;
bool     g_range_done = false;
GRBRange g_range;
long     g_last_quarter = -1;
datetime g_break_bar = 0;
int      g_break_side = 0;
long     g_break_close = 0;
int      g_m15_closed = 0;
bool     g_entry_uncertain = false;
long     g_entry_ms = 0;

// close requests in flight
struct CloseReq
  {
   ulong pos;
   int   state;
   long  ms;
  };
CloseReq g_cl[];

// own positions seen at the previous tick
ulong    g_open[];

// SL/TP exits whose ticks must be saved (deal + 60 s)
struct TicksToSave
  {
   ulong pos;
   long  deal_msc;
  };
TicksToSave g_tk[];

//+------------------------------------------------------------------+
string DayStr(const datetime d0)
  {
   return (d0 > 0) ? TimeToString(d0, TIME_DATE) : "";
  }

string SafeName(const string s)
  {
   string r = s;
   string bad[] = {"\\", "/", ":", "*", "?", "\"", "<", ">", "|", " "};
   for(int i = 0; i < ArraySize(bad); i++)
      StringReplace(r, bad[i], "_");
   return r;
  }

string GVName()
  {
   return g_base + "_started";
  }

//--- one journal line, written and closed at once (durable before any order is sent)
bool Jr(const string event, const datetime d0, const string data)
  {
   string body = StringFormat("%I64d;%I64d;%I64d;%s;%s;%s", g_seq + 1, (long)TimeGMT() * 1000,
                              g_now_msc, event, DayStr(d0), data);
   string line = GRB_Line(g_hash, body);
   int h = FileOpen(g_journal, FILE_READ | FILE_WRITE | FILE_TXT | FILE_ANSI | FILE_SHARE_READ);
   if(h == INVALID_HANDLE)
     {
      Print("GRB: journal not writable, error ", GetLastError());
      return false;
     }
   FileSeek(h, 0, SEEK_END);
   FileWriteString(h, line + "\r\n");
   FileFlush(h);
   FileClose(h);
   g_seq++;
   g_hash = GRB_Sha256(g_hash + "|" + body);
   return true;
  }

//--- reads the journal and checks the chain; a broken journal is archived and a new one is started
void LoadJournal()
  {
   ArrayResize(g_ev, 0);
   ArrayResize(g_dy, 0);
   ArrayResize(g_da, 0);
   g_jr_present = FileIsExist(g_journal);
   g_jr_intact = true;
   if(!g_jr_present)
     {
      if(g_jr_expected)
         g_jr_problem = "journal missing";
      return;
     }
   string lines[];
   int h = FileOpen(g_journal, FILE_READ | FILE_TXT | FILE_ANSI | FILE_SHARE_READ);
   if(h == INVALID_HANDLE)
     {
      g_jr_intact = false;
      g_jr_problem = "journal unreadable";
      return;
     }
   while(!FileIsEnding(h))
     {
      string r = FileReadString(h);
      if(StringLen(r) == 0)
         continue;
      int n = ArraySize(lines);
      ArrayResize(lines, n + 1);
      lines[n] = r;
     }
   FileClose(h);
   string last;
   int broken = GRB_VerifyChain(lines, last);
   if(broken >= 0)
     {
      g_jr_intact = false;
      g_jr_problem = StringFormat("journal corrupted at line %d", broken + 1);
      string archive = StringFormat("%s_corrupted_%I64d.csv", g_base, (long)TimeGMT());
      FileMove(g_journal, 0, archive, 0);
      g_hash = "GENESIS";
      g_seq = 0;
      return;
     }
   g_hash = last;
   g_seq = ArraySize(lines);
   for(int i = 0; i < ArraySize(lines); i++)
     {
      string c[];
      if(StringSplit(lines[i], ';', c) < 7)
         continue;
      int n = ArraySize(g_ev);
      ArrayResize(g_ev, n + 1);
      ArrayResize(g_dy, n + 1);
      ArrayResize(g_da, n + 1);
      g_ev[n] = c[3];
      g_dy[n] = c[4];
      g_da[n] = c[5];
     }
  }

//--- is there already a decision (or a block) for the day in the journal?
bool DecisionInJournal(const string day)
  {
   for(int i = 0; i < ArraySize(g_ev); i++)
      if(g_dy[i] == day && (g_ev[i] == "DECISION" || g_ev[i] == "BLOCK"))
         return true;
   return false;
  }

//--- was the entry of the day left uncertain (journal)?
bool EntryUncertainInJournal(const string day)
  {
   bool uncertain = false;
   for(int i = 0; i < ArraySize(g_ev); i++)
     {
      if(g_dy[i] != day)
         continue;
      if(g_ev[i] == "ENTRY_REQUEST")
         uncertain = true;                    // request without result = uncertain
      if(g_ev[i] == "ENTRY_RESULT" || g_ev[i] == "ENTRY_RESOLVED")
         uncertain = (GRB_Value(g_da[i], "state") == "UNCERTAIN");
     }
   return uncertain;
  }

//--- last state of the close request of a position in the journal
int CloseStateInJournal(const ulong pos)
  {
   int st = GRB_NOT_REQUESTED;
   string p = StringFormat("%I64u", pos);
   for(int i = 0; i < ArraySize(g_ev); i++)
     {
      if(GRB_Value(g_da[i], "pos") != p)
         continue;
      if(g_ev[i] == "CLOSE_REQUEST")
         st = GRB_UNCERTAIN;                  // request without result = uncertain
      if(g_ev[i] == "CLOSE_RESULT" || g_ev[i] == "CLOSE_RESOLVED")
         st = GRB_StateFromName(GRB_Value(g_da[i], "state"));
     }
   return st;
  }

//+------------------------------------------------------------------+
//| broker: reads                                                    |
//+------------------------------------------------------------------+
int OwnPositions(ulong &pos[])
  {
   ArrayResize(pos, 0);
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk == 0)
         continue;
      if(PositionGetString(POSITION_SYMBOL) != _Symbol || PositionGetInteger(POSITION_MAGIC) != InpMagic)
         continue;
      int n = ArraySize(pos);
      ArrayResize(pos, n + 1);
      pos[n] = (ulong)PositionGetInteger(POSITION_IDENTIFIER);
     }
   return ArraySize(pos);
  }

bool SelectPosition(const ulong pos)
  {
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk != 0 && (ulong)PositionGetInteger(POSITION_IDENTIFIER) == pos)
         return true;
     }
   return false;
  }

bool ActiveOrderFor(const ulong pos)
  {
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong tk = OrderGetTicket(i);
      if(tk == 0 || OrderGetString(ORDER_SYMBOL) != _Symbol)
         continue;
      if(pos == 0 && OrderGetInteger(ORDER_MAGIC) == InpMagic)
         return true;                         // any own order (entry)
      if(pos != 0 && (ulong)OrderGetInteger(ORDER_POSITION_ID) == pos)
         return true;
     }
   return false;
  }

//--- own entry deal of the day: 0 if none, otherwise the position identifier
ulong EntryToday(const datetime d0)
  {
   if(!HistorySelect(d0, d0 + 86400))
      return 0;
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
     {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0 || HistoryDealGetString(d, DEAL_SYMBOL) != _Symbol)
         continue;
      if(HistoryDealGetInteger(d, DEAL_MAGIC) == InpMagic && HistoryDealGetInteger(d, DEAL_ENTRY) == DEAL_ENTRY_IN)
         return (ulong)HistoryDealGetInteger(d, DEAL_POSITION_ID);
     }
   return 0;
  }

bool ActivityToday(const datetime d0)
  {
   if(EntryToday(d0) != 0 || ActiveOrderFor(0))
      return true;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong tk = PositionGetTicket(i);
      if(tk != 0 && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == InpMagic
         && (datetime)PositionGetInteger(POSITION_TIME) >= d0)
         return true;
     }
   return false;
  }

//--- the last exit deal of a position: false if there is none (yet)
bool ExitDeal(const ulong pos, ulong &deal, long &msc, double &price, long &reason)
  {
   deal = 0;
   if(!HistorySelectByPosition(pos))
      return false;
   for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
     {
      ulong d = HistoryDealGetTicket(i);
      if(d == 0)
         continue;
      long e = HistoryDealGetInteger(d, DEAL_ENTRY);
      if(e == DEAL_ENTRY_OUT || e == DEAL_ENTRY_OUT_BY)
        {
         deal = d;
         msc = HistoryDealGetInteger(d, DEAL_TIME_MSC);
         price = HistoryDealGetDouble(d, DEAL_PRICE);
         reason = HistoryDealGetInteger(d, DEAL_REASON);
         return true;
        }
     }
   return false;
  }

string ReasonName(const long r)
  {
   switch((int)r)
     {
      case DEAL_REASON_SL:     return "SL";
      case DEAL_REASON_TP:     return "TP";
      case DEAL_REASON_EXPERT: return "EXPERT";
      case DEAL_REASON_CLIENT: return "CLIENT";
      case DEAL_REASON_MOBILE: return "MOBILE";
      case DEAL_REASON_WEB:    return "WEB";
      case DEAL_REASON_SO:     return "STOP_OUT";
     }
   return StringFormat("OTHER_%d", (int)r);
  }

//+------------------------------------------------------------------+
//| close requests: state in memory                                  |
//+------------------------------------------------------------------+
int CloseIndex(const ulong pos)
  {
   for(int i = 0; i < ArraySize(g_cl); i++)
      if(g_cl[i].pos == pos)
         return i;
   int n = ArraySize(g_cl);
   ArrayResize(g_cl, n + 1);
   g_cl[n].pos = pos;
   g_cl[n].state = GRB_NOT_REQUESTED;
   g_cl[n].ms = 0;
   return n;
  }

void RemoveClose(const ulong pos)
  {
   for(int i = 0; i < ArraySize(g_cl); i++)
      if(g_cl[i].pos == pos)
        {
         for(int j = i; j < ArraySize(g_cl) - 1; j++)
            g_cl[j] = g_cl[j + 1];
         ArrayResize(g_cl, ArraySize(g_cl) - 1);
         return;
        }
  }

//+------------------------------------------------------------------+
//| exits                                                            |
//+------------------------------------------------------------------+
//--- the position is gone: log the exit (false = exit deal not in the history yet)
bool LogExit(const ulong pos)
  {
   ulong deal;
   long msc, reason;
   double price;
   if(!ExitDeal(pos, deal, msc, price, reason))
      return false;
   int i = CloseIndex(pos);
   bool requested = (g_cl[i].state != GRB_NOT_REQUESTED);
   string strategic = "OTHER";
   if(reason == DEAL_REASON_SL)
      strategic = "SL";
   else if(reason == DEAL_REASON_TP)
      strategic = "TP";
   else if(reason == DEAL_REASON_EXPERT && requested)
      strategic = "TIME";
   if(g_cl[i].state == GRB_UNCERTAIN)
      Jr("CLOSE_RESOLVED", g_d0, StringFormat("pos=%I64u,state=DONE,deal=%I64u", pos, deal));
   Jr("EXIT", g_d0, StringFormat("pos=%I64u,deal=%I64u,deal_msc=%I64d,price=%.2f,reason=%s,broker_reason=%s",
                                 pos, deal, msc, price, strategic, ReasonName(reason)));
   if(InpSaveExitTicks && (strategic == "SL" || strategic == "TP"))
     {
      int n = ArraySize(g_tk);
      ArrayResize(g_tk, n + 1);
      g_tk[n].pos = pos;
      g_tk[n].deal_msc = msc;
     }
   RemoveClose(pos);
   return true;
  }

//--- BID/ASK ticks from 2 minutes before to 1 minute after the exit deal
void SavePendingTicks()
  {
   for(int i = ArraySize(g_tk) - 1; i >= 0; i--)
     {
      if(g_now_msc < g_tk[i].deal_msc + 60000)
         continue;
      MqlTick q[];
      int n = CopyTicksRange(_Symbol, q, COPY_TICKS_INFO, (ulong)(g_tk[i].deal_msc - 120000), (ulong)(g_tk[i].deal_msc + 60000));
      if(n < 0)
         continue;                            // history not ready: retry
      string name = StringFormat("%s_ticks_%I64u.csv", g_base, g_tk[i].pos);
      int h = FileOpen(name, FILE_WRITE | FILE_TXT | FILE_ANSI);
      if(h != INVALID_HANDLE)
        {
         FileWriteString(h, "index;time_msc;bid;ask;flags\r\n");
         for(int k = 0; k < n; k++)
            FileWriteString(h, StringFormat("%d;%I64d;%.2f;%.2f;%u\r\n", k, q[k].time_msc, q[k].bid, q[k].ask, q[k].flags));
         FileClose(h);
        }
      Jr("TICKS_SAVED", g_d0, StringFormat("pos=%I64u,file=%s,ticks=%d", g_tk[i].pos, name, n));
      for(int j = i; j < ArraySize(g_tk) - 1; j++)
         g_tk[j] = g_tk[j + 1];
      ArrayResize(g_tk, ArraySize(g_tk) - 1);
     }
  }

//--- 22:00 closes and SL/TP exits
void ManageExits()
  {
   ulong now[];
   OwnPositions(now);
   // positions gone since the last tick
   for(int i = ArraySize(g_open) - 1; i >= 0; i--)
     {
      bool c = false;
      for(int j = 0; j < ArraySize(now); j++)
         if(now[j] == g_open[i])
            c = true;
      if(c)
         continue;
      if(LogExit(g_open[i]))
        {
         for(int k = i; k < ArraySize(g_open) - 1; k++)
            g_open[k] = g_open[k + 1];
         ArrayResize(g_open, ArraySize(g_open) - 1);
        }
     }
   // new positions (opened by this EA or found at restart)
   for(int j = 0; j < ArraySize(now); j++)
     {
      bool c = false;
      for(int i = 0; i < ArraySize(g_open); i++)
         if(g_open[i] == now[j])
            c = true;
      if(!c)
        {
         int n = ArraySize(g_open);
         ArrayResize(g_open, n + 1);
         g_open[n] = now[j];
        }
     }
   // 22:00 close
   for(int j = 0; j < ArraySize(now); j++)
     {
      ulong pos = now[j];
      if(!SelectPosition(pos))
         continue;
      ulong ticket = (ulong)PositionGetInteger(POSITION_TICKET);
      datetime d0p = GRB_Day0((datetime)PositionGetInteger(POSITION_TIME));
      int i = CloseIndex(pos);
      GRBCloseFacts f;
      f.position_open = true;
      f.order_active = ActiveOrderFor(pos);
      f.last_state = g_cl[i].state;
      f.ms_since_last = g_now_msc - g_cl[i].ms;
      f.exit_deal = false;
      if(f.last_state == GRB_UNCERTAIN)
        {
         ulong d;
         long m, r;
         double p;
         f.exit_deal = ExitDeal(pos, d, m, p, r);
        }
      int a = GRB_CloseAction(GRB_TimeToClose(d0p, g_now_msc), f);
      if(a == GRB_C_RESOLVED_NOT_DONE)
        {
         Jr("CLOSE_RESOLVED", g_d0, StringFormat("pos=%I64u,state=NOT_DONE", pos));
         g_cl[i].state = GRB_NOT_DONE;
         g_cl[i].ms = g_now_msc;
        }
      else if(a == GRB_C_SEND)
        {
         Jr("CLOSE_REQUEST", g_d0, StringFormat("pos=%I64u,reason=TIME", pos));
         g_cl[i].state = GRB_UNCERTAIN;        // until the result arrives, the request is in flight
         g_cl[i].ms = g_now_msc;
         trade.PositionClose(ticket);
         uint rc = trade.ResultRetcode();
         ulong deal = trade.ResultDeal();
         int st = GRB_StateFromRetcode(rc, deal);
         if(st == GRB_DONE && !(HistoryDealSelect(deal) && HistoryDealGetInteger(deal, DEAL_ENTRY) != DEAL_ENTRY_IN))
            st = GRB_UNCERTAIN;                 // "done" but the exit deal is not visible: uncertain
         Jr("CLOSE_RESULT", g_d0, StringFormat("pos=%I64u,state=%s,rc=%u,order=%I64u,deal=%I64u",
                                               pos, GRB_StateName(st), rc, trade.ResultOrder(), deal));
         g_cl[i].state = st;
         g_cl[i].ms = g_now_msc;
        }
     }
  }

//+------------------------------------------------------------------+
//| entry                                                            |
//+------------------------------------------------------------------+
void Decision(const int d, const string data)
  {
   Jr("DECISION", g_d0, StringFormat("result=%s,%s", GRB_DecisionName(d), data));
   g_decided = true;
  }

//--- an uncertain entry is resolved with today's positions, orders and deals (never a second order)
void ResolveUncertainEntry()
  {
   if(!g_entry_uncertain)
      return;
   ulong pos = EntryToday(g_d0);
   if(pos != 0)
     {
      Jr("ENTRY_RESOLVED", g_d0, StringFormat("state=DONE,position=%I64u", pos));
      g_entry_uncertain = false;
      return;
     }
   if(ActiveOrderFor(0) || g_now_msc - g_entry_ms < GRB_SETTLE_MS)
      return;
   Jr("ENTRY_RESOLVED", g_d0, "state=NOT_DONE");
   g_entry_uncertain = false;
  }

//--- checks done before sending, as the broker would do. "" = ok, otherwise the reason.
//    A failed check has the same outcome as a rejected order: the day is decided, no retry.
string PreCheck(const int side, const double slp, const double tpp)
  {
   double vmin = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double vmax = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double vstep = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   if(InpLots < vmin || InpLots > vmax)
      return StringFormat("volume %.2f outside %.2f-%.2f", InpLots, vmin, vmax);
   if(vstep > 0.0 && MathAbs(InpLots / vstep - MathRound(InpLots / vstep)) > 1e-7)
      return StringFormat("volume %.2f not a multiple of the step %.2f", InpLots, vstep);
   MqlTick q;
   if(!SymbolInfoTick(_Symbol, q))
      return "no current quote";
   double level = SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL) * _Point;
   bool stops_ok = (side == GRB_BUY)
                   ? (q.bid - slp > 0.0 && tpp - q.bid > 0.0 && q.bid - slp >= level && tpp - q.bid >= level)
                   : (slp - q.ask > 0.0 && q.ask - tpp > 0.0 && slp - q.ask >= level && q.ask - tpp >= level);
   if(!stops_ok)
      return "stops too close to the current price";
   double margin = 0.0;
   ENUM_ORDER_TYPE type = (side == GRB_BUY) ? ORDER_TYPE_BUY : ORDER_TYPE_SELL;
   if(!OrderCalcMargin(type, _Symbol, InpLots, (side == GRB_BUY) ? q.ask : q.bid, margin))
      return "margin not computable";
   if(margin > AccountInfoDouble(ACCOUNT_MARGIN_FREE))
      return "not enough free margin";
   return "";
  }

void Send(const int side, const long sl, const long tp)
  {
   double slp = NormalizeDouble(sl * g_tick, _Digits);
   double tpp = NormalizeDouble(tp * g_tick, _Digits);
   string comment = "GRB_" + TimeToString(g_d0, TIME_DATE);
   StringReplace(comment, ".", "");
   string why = PreCheck(side, slp, tpp);
   if(why != "")
     {
      Jr("ENTRY_RESULT", g_d0, StringFormat("state=REJECTED,rc=0,order=0,deal=0,position=0,price=0.00,check=%s", why));
      Print("GRB: entry not sent: ", why);
      return;
     }
   Jr("ENTRY_REQUEST", g_d0, StringFormat("side=%s,lots=%.2f,sl=%.2f,tp=%.2f,reason=ENTRY",
                                          side == GRB_BUY ? "BUY" : "SELL", InpLots, slp, tpp));
   if(side == GRB_BUY)
      trade.Buy(InpLots, _Symbol, 0.0, slp, tpp, comment);
   else
      trade.Sell(InpLots, _Symbol, 0.0, slp, tpp, comment);
   uint rc = trade.ResultRetcode();
   ulong deal = trade.ResultDeal();
   int st = GRB_StateFromRetcode(rc, deal);
   ulong pos = 0;
   if(st == GRB_DONE)
     {
      if(HistoryDealSelect(deal) && HistoryDealGetInteger(deal, DEAL_ENTRY) == DEAL_ENTRY_IN)
         pos = (ulong)HistoryDealGetInteger(deal, DEAL_POSITION_ID);
      else
         st = GRB_UNCERTAIN;                    // a positive return code is not enough: the deal is needed
     }
   Jr("ENTRY_RESULT", g_d0, StringFormat("state=%s,rc=%u,order=%I64u,deal=%I64u,position=%I64u,price=%.2f",
                                         GRB_StateName(st), rc, trade.ResultOrder(), deal, pos, trade.ResultPrice()));
   if(st == GRB_UNCERTAIN)
     {
      g_entry_uncertain = true;
      g_entry_ms = g_now_msc;
     }
  }

void ManageEntry(const MqlTick &tk)
  {
   if(g_decided)
      return;
   datetime t = tk.time;
   if(t < g_d0 + GRB_FIRST_M15 + 900)
      return;                                    // no decisive M15 bar closed yet (06:30)
   if(!SeriesInfoInteger(_Symbol, PERIOD_M1, SERIES_SYNCHRONIZED) || !SeriesInfoInteger(_Symbol, PERIOD_M15, SERIES_SYNCHRONIZED))
      return;                                    // history still synchronizing (e.g. after a restart): wait
   if(!g_range_done)
     {
      MqlRates m1[];
      int n = CopyRates(_Symbol, PERIOD_M1, g_d0 + GRB_RANGE_START_HOUR * 3600, g_d0 + GRB_RANGE_END_HOUR * 3600 - 1, m1);
      if(n < 0)
         return;                                 // history not ready: retry at the next tick
      GRB_BuildRange(g_d0, m1, g_tick, g_range);
      g_range_done = true;
      Jr("RANGE", g_d0, StringFormat("valid=%s,slots=%d,high=%I64d,low=%I64d,m1=%d,reason=%s",
                                     g_range.valid ? "yes" : "no", g_range.slots, g_range.high, g_range.low, n, g_range.reason));
      if(!g_range.valid)
        {
         Decision(GRB_D_NOT_MEASURED, "reason=" + g_range.reason);
         return;
        }
     }
   if(g_break_bar == 0)
     {
      long quarter = (long)t / 900;
      if(quarter == g_last_quarter)
         return;
      MqlRates m15[];
      int n = CopyRates(_Symbol, PERIOD_M15, g_d0 + GRB_FIRST_M15, g_d0 + GRB_LAST_M15, m15);
      if(n < 0)
         return;
      g_last_quarter = quarter;
      g_m15_closed = 0;
      for(int i = 0; i < n; i++)
         if(m15[i].time + 900 <= t)
            g_m15_closed++;
      datetime bar;
      long close_ticks;
      int side;
      int e = GRB_FirstBreak(g_d0, m15, t, g_tick, g_range, bar, close_ticks, side);
      if(e < 0)
        {
         Decision(GRB_D_NOT_MEASURED, "reason=M15 close off the tick grid");
         return;
        }
      if(e == 0)
        {
         if(t >= g_d0 + GRB_CLOSE_HOUR * 3600)
            Decision(GRB_D_NO_SIGNAL, StringFormat("m15_closed=%d", g_m15_closed));
         return;
        }
      g_break_bar = bar;
      g_break_side = side;
      g_break_close = close_ticks;
      Jr("BREAK", g_d0, StringFormat("bar=%s,close=%I64d,side=%s,m15_closed=%d",
                                     TimeToString(bar, TIME_MINUTES), close_ticks, side == GRB_BUY ? "BUY" : "SELL", g_m15_closed));
     }
   // the first quote after the close of the breakout M15 bar
   long closed_msc = (long)(g_break_bar + 900) * 1000;
   MqlTick q[];
   int k = CopyTicksRange(_Symbol, q, COPY_TICKS_INFO, (ulong)closed_msc, (ulong)g_now_msc);
   if(k <= 0)
     {
      if(g_now_msc - closed_msc > GRB_MAX_DELAY_MS)
         Decision(GRB_D_SKIPPED, "reason=tick history not available");
      return;
     }
   GRBDayFacts f;
   f.journal_expected = g_jr_expected;
   f.journal_present = g_jr_present;
   f.journal_intact = g_jr_intact;
   f.decision_logged = false;                    // g_decided is already false here
   f.broker_activity_today = ActivityToday(g_d0);
   string m;
   if(!GRB_CanDecide(f, m))
     {
      Decision(GRB_D_BLOCKED, "reason=" + m);
      return;
     }
   string reason;
   long px, sl, tp;
   int d = GRB_Decide(g_break_side, g_range, g_tick, g_d0, q[0].time_msc, q[0].bid, q[0].ask,
                      g_now_msc, g_first_tick_msc < closed_msc, reason, px, sl, tp);
   // the decision is durable BEFORE the order is sent
   Decision(d, StringFormat("side=%s,bar=%s,close=%I64d,first_msc=%I64d,bid=%.2f,ask=%.2f,price=%I64d,sl=%I64d,tp=%I64d,ticks_after_close=%d,stop_level=%I64d,reason=%s",
                            g_break_side == GRB_BUY ? "BUY" : "SELL", TimeToString(g_break_bar, TIME_MINUTES),
                            g_break_close, q[0].time_msc, q[0].bid, q[0].ask, px, sl, tp, k,
                            SymbolInfoInteger(_Symbol, SYMBOL_TRADE_STOPS_LEVEL), reason));
   if(d == GRB_D_ENTER)
      Send(g_break_side, sl, tp);
  }

//+------------------------------------------------------------------+
void NewDay(const datetime d0)
  {
   g_d0 = d0;
   g_decided = DecisionInJournal(DayStr(d0));
   g_range_done = false;
   g_last_quarter = -1;
   g_break_bar = 0;
   g_break_side = 0;
   g_break_close = 0;
   g_entry_uncertain = EntryUncertainInJournal(DayStr(d0));
   g_entry_ms = g_now_msc;
  }

//+------------------------------------------------------------------+
int OnInit()
  {
   g_tick = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_TICK_SIZE);
   if(g_tick <= 0.0)
      return INIT_FAILED;
   if(InpLots <= 0.0)
     {
      Print("GRB: InpLots must be greater than zero");
      return INIT_PARAMETERS_INCORRECT;
     }
   g_base = SafeName(StringFormat("GRB_%I64d_%s_%I64d", AccountInfoInteger(ACCOUNT_LOGIN), _Symbol, InpMagic));
   g_journal = g_base + ".csv";
   // in the Strategy Tester every run starts from an empty journal
   if(MQLInfoInteger(MQL_TESTER) && FileIsExist(g_journal))
      FileDelete(g_journal);
   trade.SetExpertMagicNumber(InpMagic);
   trade.SetTypeFillingBySymbol(_Symbol);
   trade.SetAsyncMode(false);
   g_jr_expected = GlobalVariableCheck(GVName());
   LoadJournal();
   GlobalVariableSet(GVName(), 1.0);
   Jr("START", 0, StringFormat("version=%s,magic=%I64d,account=%I64d,symbol=%s,tick=%.5f,lots=%.2f,journal=%s",
                               VERSION, InpMagic, AccountInfoInteger(ACCOUNT_LOGIN), _Symbol, g_tick, InpLots,
                               g_jr_problem == "" ? "ok" : g_jr_problem));
   // close requests left in flight: uncertain until verified
   ulong now[];
   OwnPositions(now);
   for(int j = 0; j < ArraySize(now); j++)
     {
      int i = CloseIndex(now[j]);
      g_cl[i].state = g_jr_intact ? CloseStateInJournal(now[j]) : GRB_UNCERTAIN;
      g_cl[i].ms = 0;                            // set to the time of the first tick
      int n = ArraySize(g_open);
      ArrayResize(g_open, n + 1);
      g_open[n] = now[j];
     }
   // entries done without an exit in the journal and already closed at the broker
   for(int r = 0; r < ArraySize(g_ev); r++)
     {
      string p = "";
      if((g_ev[r] == "ENTRY_RESULT" || g_ev[r] == "ENTRY_RESOLVED") && GRB_Value(g_da[r], "state") == "DONE")
         p = GRB_Value(g_da[r], "position");
      if(p == "" || p == "0")
         continue;
      bool exited = false;
      for(int s = r + 1; s < ArraySize(g_ev); s++)
         if(g_ev[s] == "EXIT" && GRB_Value(g_da[s], "pos") == p)
            exited = true;
      ulong pos = (ulong)StringToInteger(p);
      bool open = false;
      for(int j = 0; j < ArraySize(now); j++)
         if(now[j] == pos)
            open = true;
      if(!exited && !open)
        {
         int n = ArraySize(g_open);
         ArrayResize(g_open, n + 1);
         g_open[n] = pos;                        // at the first tick ManageExits finds it gone and logs the exit
        }
     }
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason)
  {
   Jr("STOP", g_d0, StringFormat("reason=%d", reason));
  }

void OnTick()
  {
   MqlTick tk;
   if(!SymbolInfoTick(_Symbol, tk))
      return;
   g_now_msc = tk.time_msc;
   if(g_first_tick_msc == 0)
     {
      g_first_tick_msc = tk.time_msc;
      for(int i = 0; i < ArraySize(g_cl); i++)
         if(g_cl[i].ms == 0)
            g_cl[i].ms = g_now_msc;
     }
   datetime d0 = GRB_Day0(tk.time);
   if(d0 != g_d0)
      NewDay(d0);
   if(g_jr_problem != "")
     {
      Jr("BLOCK", g_d0, "reason=" + g_jr_problem);   // no entries today; exits are still managed
      g_jr_problem = "";
      g_decided = true;
      g_jr_present = true;                      // from here the journal is new and intact: the block lasts only today
      g_jr_intact = true;
     }
   ManageExits();
   ResolveUncertainEntry();
   ManageEntry(tk);
   SavePendingTicks();
  }
//+------------------------------------------------------------------+
