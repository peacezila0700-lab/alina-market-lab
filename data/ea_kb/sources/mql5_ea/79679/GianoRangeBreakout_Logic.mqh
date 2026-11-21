//+------------------------------------------------------------------+
//| GianoRangeBreakout_Logic.mqh - session range breakout rule as    |
//| pure functions. No broker calls: everything can be tested        |
//| offline. Place in MQL5/Include/GianoRangeBreakout/.              |
//|                                                                  |
//| All times are broker SERVER time. Prices are converted to whole  |
//| ticks as soon as they are read, and from then on only integers   |
//| are used (no rounding surprises at half a tick).                 |
//+------------------------------------------------------------------+
#ifndef GRB_LOGIC_MQH
#define GRB_LOGIC_MQH

#define GRB_RANGE_START_HOUR 1
#define GRB_RANGE_END_HOUR   6
#define GRB_CLOSE_HOUR       22
#define GRB_SLOTS            60                  // 5-minute slots between 01:00 and 06:00
#define GRB_MIN_SLOTS        30                  // the range is valid with at least 30 slots that have quotes
#define GRB_MAX_GRID_ERROR   0.001               // max distance from the tick grid, in ticks
#define GRB_FIRST_M15        (6 * 3600 + 15 * 60)   // breakout bars: M15 opened from 06:15...
#define GRB_LAST_M15         (21 * 3600 + 30 * 60)  // ...to 21:30 included (62 bars)
#define GRB_MAX_DELAY_MS     60000               // beyond this, the first quote is not "now" any more
#define GRB_SETTLE_MS        10000               // wait before declaring an uncertain request as not done

enum GRB_SIDE { GRB_NONE = 0, GRB_BUY = 1, GRB_SELL = -1 };

// execution state of a trade request
enum GRB_STATE
  {
   GRB_NOT_REQUESTED = 0,
   GRB_DONE          = 1,
   GRB_REJECTED      = 2,
   GRB_UNCERTAIN     = 3,
   GRB_NOT_DONE      = 4    // uncertain, then resolved: no deal, no order, position unchanged
  };

// decision of the day
enum GRB_DECISION
  {
   GRB_D_NONE         = 0,
   GRB_D_ENTER        = 1,
   GRB_D_SKIPPED      = 2,
   GRB_D_NO_SIGNAL    = 3,
   GRB_D_NOT_MEASURED = 4,
   GRB_D_BLOCKED      = 5   // state cannot be rebuilt: no entries for the day
  };

// what to do about the 22:00 close of a position
enum GRB_ACTION
  {
   GRB_C_NOTHING           = 0,
   GRB_C_SEND              = 1,
   GRB_C_WAIT              = 2,
   GRB_C_RESOLVED_DONE     = 3,
   GRB_C_RESOLVED_NOT_DONE = 4
  };

struct GRBRange
  {
   bool   valid;
   int    slots;        // 5-minute slots with at least one quote
   long   high;         // in ticks
   long   low;          // in ticks
   string reason;
  };

// facts needed to know if a decision can still be taken today
struct GRBDayFacts
  {
   bool journal_expected;      // the EA already ran on this terminal
   bool journal_present;
   bool journal_intact;        // hash chain verified
   bool decision_logged;       // a decision (or a block) for today is already in the journal
   bool broker_activity_today; // positions, orders or deals of today with our magic number
  };

// facts for closing a position at 22:00
struct GRBCloseFacts
  {
   bool position_open;
   bool order_active;          // an active order linked to the position
   bool exit_deal;             // an exit deal of the position is in the history
   int  last_state;            // GRB_STATE of the last close request
   long ms_since_last;         // milliseconds since the last request or resolution
  };

//--- price -> whole number of ticks. false if the price is not on the tick grid.
bool GRB_ToTicks(const double price, const double tick, long &n)
  {
   n = 0;
   if(tick <= 0.0)
      return false;
   double q = price / tick;
   n = (long)MathRound(q);
   return MathAbs(q - (double)n) <= GRB_MAX_GRID_ERROR;
  }

datetime GRB_Day0(const datetime t)
  {
   return t - (t % 86400);
  }

//--- range from M1 bars (in ascending time order) on the grid of 60 slots
void GRB_BuildRange(const datetime day0, const MqlRates &m1[], const double tick, GRBRange &r)
  {
   r.valid = false;
   r.slots = 0;
   r.high = 0;
   r.low = 0;
   r.reason = "";
   int present[GRB_SLOTS];
   for(int k = 0; k < GRB_SLOTS; k++)
      present[k] = 0;
   datetime from = day0 + GRB_RANGE_START_HOUR * 3600;
   datetime to   = day0 + GRB_RANGE_END_HOUR * 3600;
   bool first = true;
   for(int i = 0; i < ArraySize(m1); i++)
     {
      datetime tb = m1[i].time;
      if(tb < from || tb >= to)
         continue;
      long hi, lo;
      if(!GRB_ToTicks(m1[i].high, tick, hi) || !GRB_ToTicks(m1[i].low, tick, lo))
        {
         r.reason = "price off the tick grid in the range";
         return;
        }
      present[(int)((tb - from) / 300)] = 1;
      if(first || hi > r.high)
         r.high = hi;
      if(first || lo < r.low)
         r.low = lo;
      first = false;
     }
   for(int k = 0; k < GRB_SLOTS; k++)
      r.slots += present[k];
   if(r.slots < GRB_MIN_SLOTS)
     {
      r.reason = StringFormat("range with %d slots out of %d", r.slots, GRB_SLOTS);
      return;
     }
   r.valid = true;
  }

//--- the first closed M15 bar that breaks the range. 1 = found, 0 = none, -1 = close off the grid.
//    m15 in ascending time order; "now" in server time.
int GRB_FirstBreak(const datetime day0, const MqlRates &m15[], const datetime now, const double tick,
                   const GRBRange &r, datetime &bar, long &close_ticks, int &side)
  {
   bar = 0;
   close_ticks = 0;
   side = GRB_NONE;
   for(int i = 0; i < ArraySize(m15); i++)
     {
      datetime tb = m15[i].time;
      if(tb < day0 + GRB_FIRST_M15 || tb > day0 + GRB_LAST_M15)
         continue;
      if(tb + 900 > now)
         continue;                      // not closed yet
      long c;
      if(!GRB_ToTicks(m15[i].close, tick, c))
         return -1;
      if(c > r.high)
        {
         bar = tb;
         close_ticks = c;
         side = GRB_BUY;
         return 1;
        }
      if(c < r.low)
        {
         bar = tb;
         close_ticks = c;
         side = GRB_SELL;
         return 1;
        }
     }
   return 0;
  }

//--- stop loss and take profit in whole ticks
void GRB_Levels(const int side, const GRBRange &r, long &sl, long &tp)
  {
   if(side == GRB_BUY)
     {
      sl = r.low;
      tp = 2 * r.high - r.low;
     }
   else
     {
      sl = r.high;
      tp = 2 * r.low - r.high;
     }
  }

//--- the entry price must be strictly between stop and target
bool GRB_InsideLevels(const int side, const long price, const long sl, const long tp)
  {
   if(side == GRB_BUY)
      return sl < price && price < tp;
   return tp < price && price < sl;
  }

//--- the decision on the first eligible quote.
//    first_msc, bid, ask = the first quote with time >= close of the breakout M15 bar.
//    alive_before = the EA was already receiving quotes before that bar closed (otherwise
//    the first quote went by while the EA was not running: no late entry).
int GRB_Decide(const int side, const GRBRange &r, const double tick, const datetime day0,
               const long first_msc, const double bid, const double ask,
               const long now_msc, const bool alive_before,
               string &reason, long &px, long &sl, long &tp)
  {
   px = 0;
   GRB_Levels(side, r, sl, tp);
   if(first_msc >= (long)(day0 + GRB_CLOSE_HOUR * 3600) * 1000)
     {
      reason = "no quote before 22:00";
      return GRB_D_SKIPPED;
     }
   if(!alive_before)
     {
      reason = "LATE_START: the EA was not running when the M15 bar closed";
      return GRB_D_SKIPPED;
     }
   if(now_msc - first_msc > GRB_MAX_DELAY_MS)
     {
      reason = "first quote seen too late";
      return GRB_D_SKIPPED;
     }
   double p = (side == GRB_BUY) ? ask : bid;
   if(!GRB_ToTicks(p, tick, px))
     {
      reason = "first quote off the tick grid";
      return GRB_D_NOT_MEASURED;
     }
   if(!GRB_InsideLevels(side, px, sl, tp))
     {
      reason = "entry price not between stop and target";
      return GRB_D_SKIPPED;
     }
   reason = "";
   return GRB_D_ENTER;
  }

//--- can a decision still be taken today?
bool GRB_CanDecide(const GRBDayFacts &f, string &reason)
  {
   if(f.journal_expected && !f.journal_present)
     {
      reason = "journal missing";
      return false;
     }
   if(f.journal_present && !f.journal_intact)
     {
      reason = "journal corrupted";
      return false;
     }
   if(f.decision_logged)
     {
      reason = "decision of the day already taken";
      return false;
     }
   if(f.broker_activity_today)
     {
      reason = "broker activity today without a decision in the journal";
      return false;
     }
   reason = "";
   return true;
  }

//--- state of a request from the server return code
int GRB_StateFromRetcode(const uint rc, const ulong deal)
  {
   if((rc == TRADE_RETCODE_DONE || rc == TRADE_RETCODE_DONE_PARTIAL) && deal > 0)
      return GRB_DONE;
   switch(rc)
     {
      case TRADE_RETCODE_REQUOTE:
      case TRADE_RETCODE_REJECT:
      case TRADE_RETCODE_CANCEL:
      case TRADE_RETCODE_INVALID:
      case TRADE_RETCODE_INVALID_VOLUME:
      case TRADE_RETCODE_INVALID_PRICE:
      case TRADE_RETCODE_INVALID_STOPS:
      case TRADE_RETCODE_TRADE_DISABLED:
      case TRADE_RETCODE_MARKET_CLOSED:
      case TRADE_RETCODE_NO_MONEY:
      case TRADE_RETCODE_PRICE_CHANGED:
      case TRADE_RETCODE_PRICE_OFF:
      case TRADE_RETCODE_INVALID_FILL:
      case TRADE_RETCODE_LOCKED:
      case TRADE_RETCODE_FROZEN:
      case TRADE_RETCODE_INVALID_ORDER:
      case TRADE_RETCODE_LIMIT_ORDERS:
      case TRADE_RETCODE_LIMIT_VOLUME:
      case TRADE_RETCODE_POSITION_CLOSED:
      case TRADE_RETCODE_TOO_MANY_REQUESTS:
      case TRADE_RETCODE_SERVER_DISABLES_AT:
      case TRADE_RETCODE_CLIENT_DISABLES_AT:
         return GRB_REJECTED;
     }
   return GRB_UNCERTAIN;    // timeout, connection, generic error, "done" without a deal...
  }

//--- is it time to close? From the first quote with time >= 22:00:00 of the position's
//    day, or on any later day.
bool GRB_TimeToClose(const datetime pos_day0, const long now_msc)
  {
   return now_msc >= (long)(pos_day0 + GRB_CLOSE_HOUR * 3600) * 1000;
  }

//--- only one close request in flight per position
int GRB_CloseAction(const bool is_time, const GRBCloseFacts &f)
  {
   if(!f.position_open)
      return (f.last_state == GRB_UNCERTAIN) ? GRB_C_RESOLVED_DONE : GRB_C_NOTHING;
   if(f.last_state == GRB_UNCERTAIN)
     {
      if(f.order_active || f.exit_deal || f.ms_since_last < GRB_SETTLE_MS)
         return GRB_C_WAIT;
      return GRB_C_RESOLVED_NOT_DONE;
     }
   if(!is_time)
      return GRB_C_NOTHING;
   if(f.order_active)
      return GRB_C_WAIT;
   return GRB_C_SEND;       // no request yet, or the previous one resolved (rejected or not done)
  }

//--- journal: SHA-256 hash in hex (ASCII text only)
string GRB_Sha256(const string s)
  {
   uchar data[], key[], result[];
   StringToCharArray(s, data, 0, StringLen(s), CP_UTF8);
   if(CryptEncode(CRYPT_HASH_SHA256, data, key, result) <= 0)
      return "";
   string h = "";
   for(int i = 0; i < ArraySize(result); i++)
      h += StringFormat("%02x", result[i]);
   return h;
  }

//--- journal: a line is "body;hash", with hash = SHA256(previous_hash + "|" + body)
string GRB_Line(const string previous, const string body)
  {
   return body + ";" + GRB_Sha256(previous + "|" + body);
  }

//--- chain check. Returns the index of the first bad line, or -1 if intact.
//    last = hash of the last good line.
int GRB_VerifyChain(const string &lines[], string &last)
  {
   last = "GENESIS";
   for(int i = 0; i < ArraySize(lines); i++)
     {
      int p = StringFind(lines[i], ";", 0);
      int q = -1;
      while(p >= 0)
        {
         q = p;
         p = StringFind(lines[i], ";", p + 1);
        }
      if(q <= 0)
         return i;
      string body = StringSubstr(lines[i], 0, q);
      string hash = StringSubstr(lines[i], q + 1);
      if(GRB_Sha256(last + "|" + body) != hash)
         return i;
      last = hash;
     }
   return -1;
  }

//--- value of a key in "k1=v1,k2=v2"
string GRB_Value(const string data, const string key)
  {
   string parts[];
   int n = StringSplit(data, ',', parts);
   for(int i = 0; i < n; i++)
     {
      int e = StringFind(parts[i], "=");
      if(e > 0 && StringSubstr(parts[i], 0, e) == key)
         return StringSubstr(parts[i], e + 1);
     }
   return "";
  }

string GRB_DecisionName(const int d)
  {
   switch(d)
     {
      case GRB_D_ENTER:        return "ENTER";
      case GRB_D_SKIPPED:      return "SKIPPED";
      case GRB_D_NO_SIGNAL:    return "NO_SIGNAL";
      case GRB_D_NOT_MEASURED: return "NOT_MEASURED";
      case GRB_D_BLOCKED:      return "BLOCKED";
     }
   return "NONE";
  }

string GRB_StateName(const int s)
  {
   switch(s)
     {
      case GRB_DONE:      return "DONE";
      case GRB_REJECTED:  return "REJECTED";
      case GRB_UNCERTAIN: return "UNCERTAIN";
      case GRB_NOT_DONE:  return "NOT_DONE";
     }
   return "NOT_REQUESTED";
  }

int GRB_StateFromName(const string s)
  {
   if(s == "DONE")      return GRB_DONE;
   if(s == "REJECTED")  return GRB_REJECTED;
   if(s == "UNCERTAIN") return GRB_UNCERTAIN;
   if(s == "NOT_DONE")  return GRB_NOT_DONE;
   return GRB_NOT_REQUESTED;
  }

#endif
