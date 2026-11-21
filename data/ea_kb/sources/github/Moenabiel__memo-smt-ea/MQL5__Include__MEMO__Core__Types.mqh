#ifndef MEMO_CORE_TYPES_MQH
#define MEMO_CORE_TYPES_MQH

enum MEMO_Direction
{
   MEMO_DIR_NONE = 0,
   MEMO_DIR_BUY  = 1,
   MEMO_DIR_SELL = -1
};

enum MEMO_SessionId
{
   MEMO_SESSION_NONE   = 0,
   MEMO_SESSION_ASIA   = 1,
   MEMO_SESSION_LONDON = 2,
   MEMO_SESSION_NEWYORK= 3
};

enum MEMO_SmtTier
{
   MEMO_TIER_NONE = 0,
   MEMO_TIER_1    = 1,
   MEMO_TIER_2    = 2,
   MEMO_TIER_3    = 3
};

enum MEMO_MarketRegime
{
   MEMO_REGIME_UNKNOWN      = 0,
   MEMO_REGIME_TRENDING     = 1,
   MEMO_REGIME_RANGING      = 2,
   MEMO_REGIME_EXPANSION    = 3,
   MEMO_REGIME_REVERSAL     = 4,
   MEMO_REGIME_HIGH_VOL     = 5,
   MEMO_REGIME_LOW_VOL      = 6
};

string MEMO_DirectionText(const MEMO_Direction direction)
{
   if(direction == MEMO_DIR_BUY)
      return "BUY";
   if(direction == MEMO_DIR_SELL)
      return "SELL";
   return "NONE";
}

string MEMO_SessionText(const MEMO_SessionId session)
{
   if(session == MEMO_SESSION_ASIA)
      return "ASIA";
   if(session == MEMO_SESSION_LONDON)
      return "LONDON";
   if(session == MEMO_SESSION_NEWYORK)
      return "NEWYORK";
   return "NONE";
}

string MEMO_TierText(const MEMO_SmtTier tier)
{
   if(tier == MEMO_TIER_1)
      return "TIER_1";
   if(tier == MEMO_TIER_2)
      return "TIER_2";
   if(tier == MEMO_TIER_3)
      return "TIER_3";
   return "NONE";
}

string MEMO_RegimeText(const MEMO_MarketRegime regime)
{
   switch(regime)
   {
      case MEMO_REGIME_TRENDING:  return "TRENDING";
      case MEMO_REGIME_RANGING:   return "RANGING";
      case MEMO_REGIME_EXPANSION: return "EXPANSION";
      case MEMO_REGIME_REVERSAL:  return "REVERSAL";
      case MEMO_REGIME_HIGH_VOL:  return "HIGH_VOLATILITY";
      case MEMO_REGIME_LOW_VOL:   return "LOW_VOLATILITY";
      default:                    return "UNKNOWN";
   }
}

int MEMO_MinutesOfDay(const datetime value)
{
   MqlDateTime dt;
   TimeToStruct(value, dt);
   return dt.hour * 60 + dt.min;
}

datetime MEMO_StartOfDay(const datetime value)
{
   MqlDateTime dt;
   TimeToStruct(value, dt);
   dt.hour = 0;
   dt.min = 0;
   dt.sec = 0;
   return StructToTime(dt);
}

double MEMO_ClampDouble(const double value, const double lower, const double upper)
{
   if(value < lower)
      return lower;
   if(value > upper)
      return upper;
   return value;
}

bool MEMO_InMinuteWindow(const int minute, const int start_minute, const int end_minute)
{
   if(start_minute == end_minute)
      return true;
   if(start_minute < end_minute)
      return minute >= start_minute && minute < end_minute;
   return minute >= start_minute || minute < end_minute;
}

double MEMO_NormalizePrice(const string symbol, const double price)
{
   const int digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
   return NormalizeDouble(price, digits);
}

struct MEMO_SymbolSpec
{
   string symbol;
   int    digits;
   double point;
   double tick_size;
   double tick_value;
   double volume_min;
   double volume_max;
   double volume_step;
   double stops_level_points;
   double freeze_level_points;
   bool   ready;

   void Reset()
   {
      symbol = "";
      digits = 0;
      point = 0.0;
      tick_size = 0.0;
      tick_value = 0.0;
      volume_min = 0.0;
      volume_max = 0.0;
      volume_step = 0.0;
      stops_level_points = 0.0;
      freeze_level_points = 0.0;
      ready = false;
   }
};

struct MEMO_PriceRange
{
   string   name;
   double   high;
   double   low;
   datetime start_time;
   datetime end_time;
   bool     valid;

   void Reset(const string range_name = "")
   {
      name = range_name;
      high = 0.0;
      low = 0.0;
      start_time = 0;
      end_time = 0;
      valid = false;
   }

   double Midpoint() const
   {
      return (high + low) * 0.5;
   }

   double Size() const
   {
      if(!valid)
         return 0.0;
      return MathAbs(high - low);
   }

   bool Contains(const double price) const
   {
      if(!valid)
         return false;
      return price <= high && price >= low;
   }
};

struct MEMO_LiquidityMap
{
   string symbol;
   MEMO_PriceRange previous_day;
   MEMO_PriceRange previous_week;
   MEMO_PriceRange asia;
   MEMO_PriceRange london;
   MEMO_PriceRange newyork;
   MEMO_PriceRange ny_opening_range;
   datetime updated_at;
   bool valid;

   void Reset(const string map_symbol = "")
   {
      symbol = map_symbol;
      previous_day.Reset("Previous Day");
      previous_week.Reset("Previous Week");
      asia.Reset("Asian Session");
      london.Reset("London Session");
      newyork.Reset("New York Session");
      ny_opening_range.Reset("New York Opening Range");
      updated_at = 0;
      valid = false;
   }
};

struct MEMO_LiquidityEvent
{
   bool           valid;
   string         symbol;
   MEMO_Direction direction;
   MEMO_SmtTier   tier;
   string         level_name;
   double         level_price;
   datetime       event_time;
   double         sweep_extreme;
   double         close_price;
   bool           reclaimed;
   double         distance_points;

   void Reset()
   {
      valid = false;
      symbol = "";
      direction = MEMO_DIR_NONE;
      tier = MEMO_TIER_NONE;
      level_name = "";
      level_price = 0.0;
      event_time = 0;
      sweep_extreme = 0.0;
      close_price = 0.0;
      reclaimed = false;
      distance_points = 0.0;
   }
};

struct MEMO_SMTSignal
{
   bool           valid;
   string         candidate_symbol;
   string         swept_symbol;
   MEMO_Direction direction;
   MEMO_SmtTier   tier;
   string         source_level;
   double         source_price;
   datetime       event_time;
   int            base_weight;
   int            cascade_bonus;
   bool           tier3_confirmed;
   string         reason;

   void Reset()
   {
      valid = false;
      candidate_symbol = "";
      swept_symbol = "";
      direction = MEMO_DIR_NONE;
      tier = MEMO_TIER_NONE;
      source_level = "";
      source_price = 0.0;
      event_time = 0;
      base_weight = 0;
      cascade_bonus = 0;
      tier3_confirmed = false;
      reason = "";
   }
};

struct MEMO_DisplacementSignal
{
   bool           valid;
   string         symbol;
   MEMO_Direction direction;
   datetime       bar_time;
   double         body_points;
   double         atr_points;
   double         body_ratio;
   bool           created_fvg;

   void Reset()
   {
      valid = false;
      symbol = "";
      direction = MEMO_DIR_NONE;
      bar_time = 0;
      body_points = 0.0;
      atr_points = 0.0;
      body_ratio = 0.0;
      created_fvg = false;
   }
};

struct MEMO_StructureSignal
{
   bool           valid;
   bool           mss;
   bool           choch;
   string         symbol;
   MEMO_Direction direction;
   datetime       event_time;
   double         break_level;
   string         reason;

   void Reset()
   {
      valid = false;
      mss = false;
      choch = false;
      symbol = "";
      direction = MEMO_DIR_NONE;
      event_time = 0;
      break_level = 0.0;
      reason = "";
   }
};

struct MEMO_FVGZone
{
   bool           valid;
   string         symbol;
   MEMO_Direction direction;
   datetime       left_time;
   datetime       right_time;
   double         upper;
   double         lower;
   bool           mitigated;

   void Reset()
   {
      valid = false;
      symbol = "";
      direction = MEMO_DIR_NONE;
      left_time = 0;
      right_time = 0;
      upper = 0.0;
      lower = 0.0;
      mitigated = false;
   }

   bool Contains(const double price) const
   {
      return valid && price <= upper && price >= lower;
   }
};

struct MEMO_OrderBlockZone
{
   bool           valid;
   string         symbol;
   MEMO_Direction direction;
   datetime       time;
   double         upper;
   double         lower;
   bool           breaker;
   bool           mitigated;

   void Reset()
   {
      valid = false;
      symbol = "";
      direction = MEMO_DIR_NONE;
      time = 0;
      upper = 0.0;
      lower = 0.0;
      breaker = false;
      mitigated = false;
   }

   bool Contains(const double price) const
   {
      return valid && price <= upper && price >= lower;
   }
};

struct MEMO_RegimeState
{
   bool              valid;
   string            symbol;
   MEMO_MarketRegime regime;
   double            adx;
   double            atr_points;
   double            atr_percent;
   double            range_points;
   datetime          updated_at;

   void Reset()
   {
      valid = false;
      symbol = "";
      regime = MEMO_REGIME_UNKNOWN;
      adx = 0.0;
      atr_points = 0.0;
      atr_percent = 0.0;
      range_points = 0.0;
      updated_at = 0;
   }
};

struct MEMO_ScoreBreakdown
{
   int smt;
   int cascade;
   int liquidity;
   int displacement;
   int structure;
   int premium_discount;
   int fvg;
   int order_block;
   int session_alignment;
   int correlation;
   int regime;
   int total;
   string notes;

   void Reset()
   {
      smt = 0;
      cascade = 0;
      liquidity = 0;
      displacement = 0;
      structure = 0;
      premium_discount = 0;
      fvg = 0;
      order_block = 0;
      session_alignment = 0;
      correlation = 0;
      regime = 0;
      total = 0;
      notes = "";
   }
};

struct MEMO_SetupContext
{
   bool                    valid;
   string                  symbol;
   MEMO_Direction          direction;
   MEMO_SessionId          session;
   MEMO_SMTSignal          smt;
   MEMO_LiquidityEvent     liquidity;
   MEMO_DisplacementSignal displacement;
   MEMO_StructureSignal    structure;
   MEMO_FVGZone            fvg;
   MEMO_OrderBlockZone     order_block;
   MEMO_RegimeState        regime;
   MEMO_ScoreBreakdown     score;
   double                  correlation;
   double                  entry_price;
   double                  stop_loss;
   double                  take_profit_1;
   double                  take_profit_2;
   string                  rejection_reason;

   void Reset()
   {
      valid = false;
      symbol = "";
      direction = MEMO_DIR_NONE;
      session = MEMO_SESSION_NONE;
      smt.Reset();
      liquidity.Reset();
      displacement.Reset();
      structure.Reset();
      fvg.Reset();
      order_block.Reset();
      regime.Reset();
      score.Reset();
      correlation = 0.0;
      entry_price = 0.0;
      stop_loss = 0.0;
      take_profit_1 = 0.0;
      take_profit_2 = 0.0;
      rejection_reason = "";
   }
};

#endif
