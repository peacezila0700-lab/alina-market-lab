#ifndef MEMO_ENGINES_SMT_DETECTION_ENGINE_MQH
#define MEMO_ENGINES_SMT_DETECTION_ENGINE_MQH

#include <MEMO\Core\Settings.mqh>
#include <MEMO\Engines\LiquidityEngine.mqh>
#include <MEMO\Managers\LoggingManager.mqh>

class CSMTDetectionEngine
{
private:
   MEMO_Settings m_settings;
   CLiquidityEngine *m_liquidity;
   CLoggingManager *m_log;

   int TierWeight(const MEMO_SmtTier tier) const
   {
      if(tier == MEMO_TIER_1)
         return 40;
      if(tier == MEMO_TIER_2)
         return 25;
      if(tier == MEMO_TIER_3)
         return 10;
      return 0;
   }

   bool BuildSignal(const MEMO_LiquidityEvent &swept,
                    const string candidate_symbol,
                    MEMO_SMTSignal &signal) const
   {
      if(!swept.valid || candidate_symbol == "")
         return false;

      signal.Reset();
      signal.valid = true;
      signal.candidate_symbol = candidate_symbol;
      signal.swept_symbol = swept.symbol;
      signal.direction = swept.direction;
      signal.tier = swept.tier;
      signal.source_level = swept.level_name;
      signal.source_price = swept.level_price;
      signal.event_time = swept.event_time;
      signal.base_weight = TierWeight(swept.tier);
      signal.reason = "SMT " + MEMO_DirectionText(swept.direction) + ": " + swept.symbol + " swept " + swept.level_name + ", " + candidate_symbol + " refused";
      return true;
   }

   bool DetectPairOnTimeframe(const string symbol_a,
                              const string symbol_b,
                              const MEMO_LiquidityMap &map_a,
                              const MEMO_LiquidityMap &map_b,
                              const ENUM_TIMEFRAMES timeframe,
                              const MEMO_SmtTier max_tier,
                              MEMO_SMTSignal &signal) const
   {
      signal.Reset();
      if(m_liquidity == NULL)
         return false;

      MEMO_SMTSignal best;
      best.Reset();

      for(int d = -1; d <= 1; d += 2)
      {
         const MEMO_Direction direction = (MEMO_Direction)d;
         MEMO_LiquidityEvent event_a;
         MEMO_LiquidityEvent event_b;
         m_liquidity.DetectSweep(symbol_a, map_a, timeframe, direction, max_tier, event_a);
         m_liquidity.DetectSweep(symbol_b, map_b, timeframe, direction, max_tier, event_b);

         if(event_a.valid && !event_b.valid)
         {
            MEMO_SMTSignal candidate;
            if(BuildSignal(event_a, symbol_b, candidate))
            {
               if(!best.valid || candidate.base_weight > best.base_weight || candidate.event_time > best.event_time)
                  best = candidate;
            }
         }
         else if(event_b.valid && !event_a.valid)
         {
            MEMO_SMTSignal candidate;
            if(BuildSignal(event_b, symbol_a, candidate))
            {
               if(!best.valid || candidate.base_weight > best.base_weight || candidate.event_time > best.event_time)
                  best = candidate;
            }
         }
      }

      if(!best.valid)
         return false;

      signal = best;
      return true;
   }

   bool DetectExecutionSMT(const string symbol_a,
                           const string symbol_b,
                           const ENUM_TIMEFRAMES timeframe,
                           const MEMO_Direction direction,
                           const string expected_candidate) const
   {
      if(m_liquidity == NULL)
         return false;

      MEMO_LiquidityEvent event_a;
      MEMO_LiquidityEvent event_b;
      m_liquidity.DetectSwingSweep(symbol_a, timeframe, direction, event_a);
      m_liquidity.DetectSwingSweep(symbol_b, timeframe, direction, event_b);

      if(event_a.valid && !event_b.valid && expected_candidate == symbol_b)
         return true;
      if(event_b.valid && !event_a.valid && expected_candidate == symbol_a)
         return true;

      return false;
   }

   int CascadeBonus(const string symbol_a,
                    const string symbol_b,
                    const MEMO_LiquidityMap &map_a,
                    const MEMO_LiquidityMap &map_b,
                    const MEMO_SMTSignal &base_signal) const
   {
      int aligned = 0;
      MEMO_SMTSignal probe;

      if(DetectPairOnTimeframe(symbol_a, symbol_b, map_a, map_b, PERIOD_H4, MEMO_TIER_2, probe)
         && probe.direction == base_signal.direction
         && probe.candidate_symbol == base_signal.candidate_symbol)
         aligned++;

      if(DetectPairOnTimeframe(symbol_a, symbol_b, map_a, map_b, PERIOD_H1, MEMO_TIER_2, probe)
         && probe.direction == base_signal.direction
         && probe.candidate_symbol == base_signal.candidate_symbol)
         aligned++;

      if(DetectPairOnTimeframe(symbol_a, symbol_b, map_a, map_b, PERIOD_M15, MEMO_TIER_2, probe)
         && probe.direction == base_signal.direction
         && probe.candidate_symbol == base_signal.candidate_symbol)
         aligned++;

      if(DetectPairOnTimeframe(symbol_a, symbol_b, map_a, map_b, PERIOD_M5, MEMO_TIER_2, probe)
         && probe.direction == base_signal.direction
         && probe.candidate_symbol == base_signal.candidate_symbol)
         aligned++;

      if(aligned >= 3)
         return 20;
      if(aligned == 2)
         return 12;
      if(aligned == 1)
         return 6;
      return 0;
   }

public:
   CSMTDetectionEngine()
   {
      m_liquidity = NULL;
      m_log = NULL;
   }

   void Init(const MEMO_Settings &settings, CLiquidityEngine *liquidity_engine, CLoggingManager *logger)
   {
      m_settings = settings;
      m_liquidity = liquidity_engine;
      m_log = logger;
   }

   bool Detect(const string symbol_a,
               const string symbol_b,
               const MEMO_LiquidityMap &map_a,
               const MEMO_LiquidityMap &map_b,
               MEMO_SMTSignal &signal) const
   {
      signal.Reset();

      if(!DetectPairOnTimeframe(symbol_a, symbol_b, map_a, map_b, m_settings.execution_tf, MEMO_TIER_2, signal))
      {
         if(m_log != NULL)
            m_log.Decision("SMTDetectionEngine", symbol_a + "/" + symbol_b, "SMT", "REJECT", 0.0, "No tier 1/2 SMT");
         return false;
      }

      signal.cascade_bonus = CascadeBonus(symbol_a, symbol_b, map_a, map_b, signal);
      signal.tier3_confirmed =
         DetectExecutionSMT(symbol_a, symbol_b, PERIOD_M1, signal.direction, signal.candidate_symbol)
      || DetectExecutionSMT(symbol_a, symbol_b, PERIOD_M3, signal.direction, signal.candidate_symbol)
      || DetectExecutionSMT(symbol_a, symbol_b, PERIOD_M5, signal.direction, signal.candidate_symbol);

      if(signal.tier3_confirmed)
         signal.reason += " + tier-3 execution SMT";

      if(signal.cascade_bonus > 0)
         signal.reason += " + cascade bonus " + IntegerToString(signal.cascade_bonus);

      if(m_log != NULL)
         m_log.Decision("SMTDetectionEngine", signal.candidate_symbol, "SMT", "ACCEPT", signal.base_weight + signal.cascade_bonus, signal.reason);

      return true;
   }
};

#endif
