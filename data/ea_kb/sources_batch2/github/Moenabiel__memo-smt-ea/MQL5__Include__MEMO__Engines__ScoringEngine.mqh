#ifndef MEMO_ENGINES_SCORING_ENGINE_MQH
#define MEMO_ENGINES_SCORING_ENGINE_MQH

#include <MEMO\Core\Settings.mqh>
#include <MEMO\Managers\LoggingManager.mqh>

class CScoringEngine
{
private:
   MEMO_Settings m_settings;
   CLoggingManager *m_log;

public:
   CScoringEngine()
   {
      m_log = NULL;
   }

   void Init(const MEMO_Settings &settings, CLoggingManager *logger)
   {
      m_settings = settings;
      m_log = logger;
   }

   void Calculate(MEMO_SetupContext &context,
                  const bool premium_discount_ok,
                  const bool fvg_retest,
                  const bool order_block_retest,
                  const bool session_aligned,
                  const int correlation_score,
                  const int regime_score) const
   {
      context.score.Reset();

      context.score.smt = context.smt.valid ? context.smt.base_weight : 0;
      context.score.cascade = context.smt.valid ? context.smt.cascade_bonus : 0;
      context.score.liquidity = context.liquidity.valid ? 15 : 0;
      context.score.displacement = context.displacement.valid ? 15 : 0;
      context.score.structure = context.structure.valid ? 20 : 0;
      context.score.premium_discount = premium_discount_ok ? 10 : 0;
      context.score.fvg = fvg_retest ? 10 : 0;
      context.score.order_block = order_block_retest ? 10 : 0;
      context.score.session_alignment = session_aligned ? 10 : 0;
      context.score.correlation = correlation_score;
      context.score.regime = regime_score;

      context.score.total =
         context.score.smt
       + context.score.cascade
       + context.score.liquidity
       + context.score.displacement
       + context.score.structure
       + context.score.premium_discount
       + context.score.fvg
       + context.score.order_block
       + context.score.session_alignment
       + context.score.correlation
       + context.score.regime;

      context.score.notes =
         "SMT=" + IntegerToString(context.score.smt)
       + " Cascade=" + IntegerToString(context.score.cascade)
       + " Liquidity=" + IntegerToString(context.score.liquidity)
       + " Displacement=" + IntegerToString(context.score.displacement)
       + " Structure=" + IntegerToString(context.score.structure)
       + " PD=" + IntegerToString(context.score.premium_discount)
       + " FVG=" + IntegerToString(context.score.fvg)
       + " OB=" + IntegerToString(context.score.order_block)
       + " Session=" + IntegerToString(context.score.session_alignment)
       + " Corr=" + IntegerToString(context.score.correlation)
       + " Regime=" + IntegerToString(context.score.regime)
       + " Total=" + IntegerToString(context.score.total);

      if(m_log != NULL)
         m_log.Decision("ScoringEngine", context.symbol, "Score",
                        context.score.total >= m_settings.confidence_threshold ? "ACCEPT" : "REJECT",
                        context.score.total, context.score.notes);
   }

   bool Passes(const MEMO_SetupContext &context, string &reason) const
   {
      if(context.score.total < m_settings.confidence_threshold)
      {
         reason = "Confidence below threshold: " + IntegerToString(context.score.total)
                + " < " + IntegerToString(m_settings.confidence_threshold);
         return false;
      }

      reason = "Confidence accepted: " + IntegerToString(context.score.total);
      return true;
   }
};

#endif
