//+------------------------------------------------------------------+
//|                                               NewsDayBlocker.mq5 |
//|  Blocks new trades on US inflation (CPI) and Fed decision (FOMC) |
//|  days, by New York date. Built-in calendar 2015-2027 (sources:   |
//|  bls.gov and federalreserve.gov), so it also works in backtests. |
//|                                                                  |
//|  On a news day it:                                               |
//|   - closes any position opened that day (manual or by any EA,    |
//|     optional magic filter),                                      |
//|   - deletes pending orders (optional),                           |
//|   - closes positions still open at a chosen New York time        |
//|     (optional, e.g. 08:25 before the 08:30 CPI release),          |
//|   - sets the terminal global variable NEWS_DAY_BLOCK = 1 so your |
//|     own EAs can check it before trading.                         |
//|  Attach to ONE chart. It never opens trades.                     |
//+------------------------------------------------------------------+
#property copyright "Augusto Martin D'anna"
#property version   "1.00"
#property description "Blocks new trades on US CPI and FOMC days (New York date). Built-in calendar 2015-2027, works in the tester."
#property description "Closes positions opened on those days, optionally deletes pending orders and closes open trades before the release."

#include <Trade/Trade.mqh>
#include "NyTime.mqh"

input ENUM_SERVER_CLOCK InpClock       = CLOCK_NY7; // Broker server clock
input bool              InpCloseNew    = true;      // Close positions opened on a news day
input bool              InpDelPending  = true;      // Delete pending orders on a news day
input int               InpCloseOpenNy = -1;        // Close open positions at, minutes after 00:00 NY (-1 = off, 505 = 08:25)
input string            InpMagics      = "";        // Only these magic numbers, comma separated (empty = all, 0 = manual)
input bool              InpPanel       = true;      // Show status on the chart

#define GV_NEWS "NEWS_DAY_BLOCK"

// US CPI release days and FOMC decision days, New York date (yyyy.mm.dd). Update every year.
const string NEWS_DAYS =
   "2015.01.16,2015.01.28,2015.02.26,2015.03.18,2015.03.24,2015.04.17,2015.04.29,2015.05.22,2015.06.17,2015.06.18," +
   "2015.07.17,2015.07.29,2015.08.19,2015.09.16,2015.09.17,2015.10.15,2015.10.28,2015.11.17,2015.12.15,2015.12.16," +
   "2016.01.20,2016.01.27,2016.02.19,2016.03.16,2016.04.14,2016.04.27,2016.05.17,2016.06.15,2016.06.16,2016.07.15," +
   "2016.07.27,2016.08.16,2016.09.16,2016.09.21,2016.10.18,2016.11.02,2016.11.17,2016.12.14,2016.12.15,2017.01.18," +
   "2017.02.01,2017.02.15,2017.03.15,2017.04.14,2017.05.03,2017.05.12,2017.06.14,2017.07.14,2017.07.26,2017.08.11," +
   "2017.09.14,2017.09.20,2017.10.13,2017.11.01,2017.11.15,2017.12.13,2018.01.12,2018.01.31,2018.02.14,2018.03.13," +
   "2018.03.21,2018.04.11,2018.05.02,2018.05.10,2018.06.12,2018.06.13,2018.07.12,2018.08.01,2018.08.10,2018.09.13," +
   "2018.09.26,2018.10.11,2018.11.08,2018.11.14,2018.12.12,2018.12.19,2019.01.11,2019.01.30,2019.02.13,2019.03.12," +
   "2019.03.20,2019.04.10,2019.05.01,2019.05.10,2019.06.12,2019.06.19,2019.07.11,2019.07.31,2019.08.13,2019.09.12," +
   "2019.09.18,2019.10.10,2019.10.30,2019.11.13,2019.12.11,2020.01.14,2020.01.29,2020.02.13,2020.03.11,2020.04.10," +
   "2020.04.29,2020.05.12,2020.06.10,2020.07.14,2020.07.29,2020.08.12,2020.09.11,2020.09.16,2020.10.13,2020.11.05," +
   "2020.11.12,2020.12.10,2020.12.16,2021.01.13,2021.01.27,2021.02.10,2021.03.10,2021.03.17,2021.04.13,2021.04.28," +
   "2021.05.12,2021.06.10,2021.06.16,2021.07.13,2021.07.28,2021.08.11,2021.09.14,2021.09.22,2021.10.13,2021.11.03," +
   "2021.11.10,2021.12.10,2021.12.15,2022.01.12,2022.01.26,2022.02.10,2022.03.10,2022.03.16,2022.04.12,2022.05.04," +
   "2022.05.11,2022.06.10,2022.06.15,2022.07.13,2022.07.27,2022.08.10,2022.09.13,2022.09.21,2022.10.13,2022.11.02," +
   "2022.11.10,2022.12.13,2022.12.14,2023.01.12,2023.02.01,2023.02.14,2023.03.14,2023.03.22,2023.04.12,2023.05.03," +
   "2023.05.10,2023.06.13,2023.06.14,2023.07.12,2023.07.26,2023.08.10,2023.09.13,2023.09.20,2023.10.12,2023.11.01," +
   "2023.11.14,2023.12.12,2023.12.13,2024.01.11,2024.01.31,2024.02.13,2024.03.12,2024.03.20,2024.04.10,2024.05.01," +
   "2024.05.15,2024.06.12,2024.07.11,2024.07.31,2024.08.14,2024.09.11,2024.09.18,2024.10.10,2024.11.07,2024.11.13," +
   "2024.12.11,2024.12.18,2025.01.15,2025.01.29,2025.02.12,2025.03.12,2025.03.19,2025.04.10,2025.05.07,2025.05.13," +
   "2025.06.11,2025.06.18,2025.07.15,2025.07.30,2025.08.12,2025.09.11,2025.09.17,2025.10.24,2025.10.29,2025.12.10," +
   "2025.12.18,2026.01.13,2026.01.28,2026.02.13,2026.03.11,2026.03.18,2026.04.10,2026.04.29,2026.05.12,2026.06.10," +
   "2026.06.17,2026.07.14,2026.07.29,2026.08.12,2026.09.11,2026.09.16,2026.10.14,2026.10.28,2026.11.10,2026.12.09," +
   "2026.12.10,2027.01.13,2027.01.27,2027.02.11,2027.03.10,2027.03.17,2027.04.13,2027.04.28,2027.05.12,2027.06.09," +
   "2027.06.10,2027.07.14,2027.07.28,2027.08.11,2027.09.14,2027.09.15,2027.10.14,2027.10.27,2027.11.10,2027.12.08," +
   "2027.12.10";

CTrade g_trade;
long   g_days[];
long   g_magics[];
long   g_closedDay = -1;
int    g_actions = 0;

void LoadDays()
  {
   string f[];
   int n = StringSplit(NEWS_DAYS, ',', f);
   ArrayResize(g_days, n);
   for(int i = 0; i < n; i++) g_days[i] = (long)StringToTime(f[i]) / 86400;
   ArraySort(g_days);
  }

void ParseMagics()
  {
   string parts[];
   int n = StringSplit(InpMagics, ',', parts);
   ArrayResize(g_magics, 0);
   for(int i = 0; i < n; i++)
     {
      string s = parts[i];
      StringTrimLeft(s); StringTrimRight(s);
      if(s == "") continue;
      int k = ArraySize(g_magics);
      ArrayResize(g_magics, k + 1);
      g_magics[k] = StringToInteger(s);
     }
  }

bool Watched(long magic)
  {
   int n = ArraySize(g_magics);
   if(n == 0) return true;
   for(int i = 0; i < n; i++) if(g_magics[i] == magic) return true;
   return false;
  }

bool IsNewsDay(long day)
  {
   int k = ArrayBsearch(g_days, day);
   return k >= 0 && k < ArraySize(g_days) && g_days[k] == day;
  }

long NextNewsDay(long day)
  {
   for(int i = 0; i < ArraySize(g_days); i++) if(g_days[i] >= day) return g_days[i];
   return -1;
  }

void Enforce()
  {
   datetime ny = NyTimeFromServer(TimeCurrent(), InpClock);
   long day = NyDayNumber(ny);
   bool news = IsNewsDay(day);
   GlobalVariableSet(GV_NEWS, news ? 1 : 0);
   if(!news) return;
   bool closeAll = InpCloseOpenNy >= 0 && NyMinute(ny) >= InpCloseOpenNy && g_closedDay != day;
   for(int i = PositionsTotal() - 1; i >= 0; i--)
     {
      ulong t = PositionGetTicket(i);
      if(t == 0 || !Watched(PositionGetInteger(POSITION_MAGIC))) continue;
      long openedDay = NyDayNumber(NyTimeFromServer((datetime)PositionGetInteger(POSITION_TIME), InpClock));
      if((InpCloseNew && openedDay == day) || closeAll)
        {
         string why = openedDay == day ? "opened on a news day" : "open at the pre-release close time";
         if(g_trade.PositionClose(t)) { g_actions++; PrintFormat("News day: closed #%I64u on %s (%s)", t, PositionGetString(POSITION_SYMBOL), why); }
        }
     }
   if(closeAll) g_closedDay = day;
   if(!InpDelPending) return;
   for(int i = OrdersTotal() - 1; i >= 0; i--)
     {
      ulong t = OrderGetTicket(i);
      if(t == 0 || !Watched(OrderGetInteger(ORDER_MAGIC))) continue;
      if(g_trade.OrderDelete(t)) { g_actions++; PrintFormat("News day: deleted pending order #%I64u", t); }
     }
  }

void Panel()
  {
   if(!InpPanel) return;
   datetime ny = NyTimeFromServer(TimeCurrent(), InpClock);
   long day = NyDayNumber(ny), next = NextNewsDay(day);
   Comment(StringFormat("News Day Blocker\nNew York: %s\nToday: %s\nNext CPI/FOMC day: %s\nActions so far: %d",
                        TimeToString(ny, TIME_DATE | TIME_MINUTES), IsNewsDay(day) ? "NEWS DAY - new trades blocked" : "normal day",
                        next < 0 ? "calendar ended, update the EA" : TimeToString((datetime)(next * 86400), TIME_DATE), g_actions));
  }

int OnInit()
  {
   LoadDays();
   ParseMagics();
   g_trade.SetDeviationInPoints(50);
   long last = g_days[ArraySize(g_days) - 1];
   long today = NyDayNumber(NyTimeFromServer(TimeCurrent(), InpClock));
   if(last - today < 60) Print("Warning: the built-in calendar ends on ", TimeToString((datetime)(last * 86400), TIME_DATE), ". Update the EA.");
   EventSetTimer(1);
   Enforce();
   Panel();
   return INIT_SUCCEEDED;
  }

void OnDeinit(const int reason) { EventKillTimer(); Comment(""); }
void OnTimer() { Enforce(); Panel(); }
void OnTick() {}
void OnTradeTransaction(const MqlTradeTransaction &tr, const MqlTradeRequest &rq, const MqlTradeResult &rs)
  {
   if(tr.type == TRADE_TRANSACTION_DEAL_ADD || tr.type == TRADE_TRANSACTION_ORDER_ADD) Enforce();
  }
//+------------------------------------------------------------------+
