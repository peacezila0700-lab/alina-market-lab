#ifndef MEMO_CORE_SETTINGS_MQH
#define MEMO_CORE_SETTINGS_MQH

#include <MEMO\Core\Types.mqh>

struct MEMO_Settings
{
   string symbol_a;
   string symbol_b;
   long   magic_number;
   int    timer_seconds;
   bool   debug_mode;
   bool   enable_visuals;
   bool   allow_live_trading;

   ENUM_TIMEFRAMES execution_tf;
   ENUM_TIMEFRAMES structure_tf;
   ENUM_TIMEFRAMES correlation_tf;
   int    analysis_bars;

   int asia_start_minute;
   int asia_end_minute;
   int london_start_minute;
   int london_end_minute;
   int newyork_start_minute;
   int newyork_end_minute;
   int ny_opening_range_minutes;
   bool trade_asia;
   bool trade_london;
   bool trade_newyork;

   int    sweep_lookback_bars;
   double sweep_buffer_points;
   double equal_level_tolerance_points;

   int    correlation_lookback;
   double minimum_correlation;

   int    atr_period;
   double minimum_displacement_points;
   double displacement_atr_multiple;
   double minimum_body_ratio;
   int    consecutive_imbalance_candles;

   int structure_lookback_bars;
   int swing_depth;

   double minimum_fvg_points;
   double maximum_fvg_points;
   double entry_sensitivity_points;
   int    order_block_lookback_bars;

   int confidence_threshold;
   bool enable_range_smt;
   bool enable_trend_smt;
   bool enable_expansion_smt;
   bool enable_reversal_smt;

   bool   use_dynamic_risk;
   double fixed_lots;
   bool   use_fixed_lots;
   double base_risk_percent;
   double risk_score_70_79;
   double risk_score_80_89;
   double risk_score_90_plus;
   double daily_drawdown_limit_percent;
   double weekly_drawdown_limit_percent;
   double session_drawdown_limit_percent;
   int    max_trades_per_day;
   int    max_trades_per_session;
   int    max_daily_losses;
   int    max_session_losses;
   int    consecutive_loss_limit;

   bool   enable_break_even;
   double break_even_r_multiple;
   double break_even_lock_points;
   bool   enable_partial_take_profit;
   double partial_close_percent;
   double tp1_r_multiple;
   double tp2_r_multiple;
   bool   enable_atr_trailing;
   double atr_trailing_multiple;
   bool   enable_structure_trailing;
   bool   enable_fvg_trailing;

   bool   enable_news_filter;
   string news_blackout_file;
   bool   block_high_impact_news;
   bool   block_medium_impact_news;
   int    news_minutes_before;
   int    news_minutes_after;

   int    panel_corner;
   color  buy_color;
   color  sell_color;
   color  neutral_color;

   void Normalize()
   {
      if(timer_seconds < 1)
         timer_seconds = 1;
      if(analysis_bars < 100)
         analysis_bars = 100;
      if(sweep_lookback_bars < 2)
         sweep_lookback_bars = 2;
      if(correlation_lookback < 20)
         correlation_lookback = 20;
      minimum_correlation = MEMO_ClampDouble(minimum_correlation, -1.0, 1.0);
      if(atr_period < 2)
         atr_period = 14;
      if(structure_lookback_bars < 10)
         structure_lookback_bars = 10;
      if(swing_depth < 1)
         swing_depth = 2;
      if(confidence_threshold < 1)
         confidence_threshold = 70;
      base_risk_percent = MEMO_ClampDouble(base_risk_percent, 0.01, 10.0);
      risk_score_70_79 = MEMO_ClampDouble(risk_score_70_79, 0.01, 10.0);
      risk_score_80_89 = MEMO_ClampDouble(risk_score_80_89, 0.01, 10.0);
      risk_score_90_plus = MEMO_ClampDouble(risk_score_90_plus, 0.01, 10.0);
      partial_close_percent = MEMO_ClampDouble(partial_close_percent, 1.0, 95.0);
      if(tp1_r_multiple <= 0.0)
         tp1_r_multiple = 1.0;
      if(tp2_r_multiple <= tp1_r_multiple)
         tp2_r_multiple = tp1_r_multiple + 1.0;
      if(news_minutes_before < 0)
         news_minutes_before = 0;
      if(news_minutes_after < 0)
         news_minutes_after = 0;
   }
};

int MEMO_ParseHHMM(const string value, const int fallback_minutes)
{
   string parts[];
   const int count = StringSplit(value, (ushort)':', parts);
   if(count != 2)
      return fallback_minutes;

   const int hours = (int)StringToInteger(parts[0]);
   const int minutes = (int)StringToInteger(parts[1]);
   if(hours < 0 || hours > 23 || minutes < 0 || minutes > 59)
      return fallback_minutes;

   return hours * 60 + minutes;
}

#endif
