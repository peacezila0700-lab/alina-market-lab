#ifndef MEMO_ENGINES_MARKET_REGIME_ENGINE_MQH
#define MEMO_ENGINES_MARKET_REGIME_ENGINE_MQH

#include <MEMO\Core\Settings.mqh>
#include <MEMO\Core\MarketData.mqh>
#include <MEMO\Managers\LoggingManager.mqh>

class CMarketRegimeEngine
{
private:
   MEMO_Settings m_settings;
   CLoggingManager *m_log;

public:
   CMarketRegimeEngine()
   {
      m_log = NULL;
   }

   void Init(const MEMO_Settings &settings, CLoggingManager *logger)
   {
      m_settings = settings;
      m_log = logger;
   }

   bool Detect(const string symbol, MEMO_RegimeState &state) const
   {
      state.Reset();

      MqlRates rates[];
      if(!MEMO_CopyRatesSeries(symbol, m_settings.structure_tf, 0, 60, rates))
         return false;

      const double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      const double price = MEMO_MidPrice(symbol);
      if(point <= 0.0 || price <= 0.0)
         return false;

      double range_high = rates[1].high;
      double range_low = rates[1].low;
      for(int i = 1; i < MathMin(30, ArraySize(rates)); i++)
      {
         range_high = MathMax(range_high, rates[i].high);
         range_low = MathMin(range_low, rates[i].low);
      }

      state.valid = true;
      state.symbol = symbol;
      state.adx = MEMO_ADXValue(symbol, m_settings.structure_tf, 14, 1);
      state.atr_points = MEMO_ATRPoints(symbol, m_settings.structure_tf, m_settings.atr_period, 1);
      state.atr_percent = (state.atr_points * point) / price;
      state.range_points = (range_high - range_low) / point;
      state.updated_at = TimeCurrent();

      const double last_body_points = MathAbs(rates[1].close - rates[1].open) / point;
      if(state.atr_percent >= 0.006)
         state.regime = MEMO_REGIME_HIGH_VOL;
      else if(state.atr_percent <= 0.001)
         state.regime = MEMO_REGIME_LOW_VOL;
      else if(state.atr_points > 0.0 && last_body_points >= state.atr_points * 1.5)
         state.regime = MEMO_REGIME_EXPANSION;
      else if(state.adx >= 25.0)
         state.regime = MEMO_REGIME_TRENDING;
      else if(state.adx <= 18.0)
         state.regime = MEMO_REGIME_RANGING;
      else
         state.regime = MEMO_REGIME_REVERSAL;

      if(m_log != NULL)
         m_log.Debug("MarketRegimeEngine", symbol + " regime=" + MEMO_RegimeText(state.regime)
                     + " adx=" + DoubleToString(state.adx, 1)
                     + " atr%=" + DoubleToString(state.atr_percent * 100.0, 2));

      return true;
   }

   bool IsAllowed(const MEMO_RegimeState &state, string &reason) const
   {
      if(!state.valid)
      {
         reason = "Regime unavailable";
         return false;
      }

      if(state.regime == MEMO_REGIME_RANGING && !m_settings.enable_range_smt)
      {
         reason = "Range SMT disabled";
         return false;
      }
      if(state.regime == MEMO_REGIME_TRENDING && !m_settings.enable_trend_smt)
      {
         reason = "Trend SMT disabled";
         return false;
      }
      if(state.regime == MEMO_REGIME_EXPANSION && !m_settings.enable_expansion_smt)
      {
         reason = "Expansion SMT disabled";
         return false;
      }
      if(state.regime == MEMO_REGIME_REVERSAL && !m_settings.enable_reversal_smt)
      {
         reason = "Reversal SMT disabled";
         return false;
      }

      reason = "Regime allowed: " + MEMO_RegimeText(state.regime);
      return true;
   }

   int Score(const MEMO_RegimeState &state) const
   {
      if(!state.valid)
         return 0;
      if(state.regime == MEMO_REGIME_HIGH_VOL)
         return 6;
      if(state.regime == MEMO_REGIME_LOW_VOL)
         return 4;
      return 10;
   }
};

#endif
