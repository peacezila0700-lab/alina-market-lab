#property strict
#property version   "1.00"
#property description "MEMO XAU/XAG institutional SMT Expert Advisor"

#include <MEMO\Core\Settings.mqh>
#include <MEMO\Core\MarketData.mqh>
#include <MEMO\Managers\LoggingManager.mqh>
#include <MEMO\Managers\SymbolManager.mqh>
#include <MEMO\Managers\SessionManager.mqh>
#include <MEMO\Managers\NewsFilter.mqh>
#include <MEMO\Managers\RiskManager.mqh>
#include <MEMO\Managers\TradeManager.mqh>
#include <MEMO\Managers\StatisticsManager.mqh>
#include <MEMO\Managers\VisualizationManager.mqh>
#include <MEMO\Engines\LiquidityEngine.mqh>
#include <MEMO\Engines\SMTDetectionEngine.mqh>
#include <MEMO\Engines\CorrelationEngine.mqh>
#include <MEMO\Engines\DisplacementEngine.mqh>
#include <MEMO\Engines\MarketStructureEngine.mqh>
#include <MEMO\Engines\PremiumDiscountEngine.mqh>
#include <MEMO\Engines\FVGEngine.mqh>
#include <MEMO\Engines\OrderBlockEngine.mqh>
#include <MEMO\Engines\MarketRegimeEngine.mqh>
#include <MEMO\Engines\ScoringEngine.mqh>

input group "General"
input string InpSymbolA = "XAUUSD";
input string InpSymbolB = "XAGUSD";
input long   InpMagicNumber = 26061701;
input bool   InpAllowLiveTrading = false;
input bool   InpDebugMode = true;
input bool   InpEnableVisuals = true;
input int    InpTimerSeconds = 5;

input group "Timeframes"
input ENUM_TIMEFRAMES InpExecutionTF = PERIOD_M5;
input ENUM_TIMEFRAMES InpStructureTF = PERIOD_M15;
input ENUM_TIMEFRAMES InpCorrelationTF = PERIOD_M15;
input int InpAnalysisBars = 500;

input group "Sessions Broker Time"
input string InpAsiaStart = "00:00";
input string InpAsiaEnd = "06:00";
input string InpLondonStart = "07:00";
input string InpLondonEnd = "11:00";
input string InpNewYorkStart = "13:30";
input string InpNewYorkEnd = "17:00";
input int    InpNYOpeningRangeMinutes = 30;
input bool   InpTradeAsia = false;
input bool   InpTradeLondon = true;
input bool   InpTradeNewYork = true;

input group "Liquidity And SMT"
input int    InpSweepLookbackBars = 8;
input double InpSweepBufferPoints = 5.0;
input double InpEqualLevelTolerancePoints = 10.0;
input int    InpCorrelationLookback = 96;
input double InpMinimumCorrelation = 0.55;

input group "Displacement And Structure"
input int    InpATRPeriod = 14;
input double InpMinimumDisplacementPoints = 80.0;
input double InpDisplacementATRMultiple = 1.00;
input double InpMinimumBodyRatio = 0.60;
input int    InpConsecutiveImbalanceCandles = 1;
input int    InpStructureLookbackBars = 80;
input int    InpSwingDepth = 2;

input group "Arrays"
input double InpMinimumFVGPoints = 15.0;
input double InpMaximumFVGPoints = 500.0;
input double InpEntrySensitivityPoints = 10.0;
input int    InpOrderBlockLookbackBars = 40;

input group "Scoring"
input int  InpConfidenceThreshold = 70;
input bool InpEnableRangeSMT = true;
input bool InpEnableTrendSMT = true;
input bool InpEnableExpansionSMT = true;
input bool InpEnableReversalSMT = true;

input group "Risk"
input bool   InpUseDynamicRisk = true;
input bool   InpUseFixedLots = false;
input double InpFixedLots = 0.01;
input double InpBaseRiskPercent = 0.50;
input double InpRiskScore70To79 = 0.25;
input double InpRiskScore80To89 = 0.50;
input double InpRiskScore90Plus = 0.75;
input double InpDailyDrawdownLimitPercent = 3.0;
input double InpWeeklyDrawdownLimitPercent = 6.0;
input double InpSessionDrawdownLimitPercent = 1.5;
input int    InpMaxTradesPerDay = 4;
input int    InpMaxTradesPerSession = 2;
input int    InpMaxDailyLosses = 4;
input int    InpMaxSessionLosses = 2;
input int    InpConsecutiveLossLimit = 4;

input group "Trade Management"
input bool   InpEnableBreakEven = true;
input double InpBreakEvenRMultiple = 1.0;
input double InpBreakEvenLockPoints = 5.0;
input bool   InpEnablePartialTakeProfit = true;
input double InpPartialClosePercent = 50.0;
input double InpTP1RMultiple = 1.0;
input double InpTP2RMultiple = 2.5;
input bool   InpEnableATRTrailing = true;
input double InpATRTrailingMultiple = 1.5;
input bool   InpEnableStructureTrailing = true;
input bool   InpEnableFVGTrailing = false;

input group "News"
input bool   InpEnableNewsFilter = true;
input string InpNewsBlackoutFile = "MEMO_NewsBlackouts.csv";
input bool   InpBlockHighImpactNews = true;
input bool   InpBlockMediumImpactNews = false;
input int    InpNewsMinutesBefore = 30;
input int    InpNewsMinutesAfter = 15;

input group "Visuals"
input int   InpPanelCorner = CORNER_LEFT_UPPER;
input color InpBuyColor = clrMediumSeaGreen;
input color InpSellColor = clrTomato;
input color InpNeutralColor = clrSilver;

MEMO_Settings g_settings;
CLoggingManager g_log;
CSymbolManager g_symbols;
CSessionManager g_sessions;
CNewsFilter g_news;
CRiskManager g_risk;
CTradeManager g_trade;
CStatisticsManager g_stats;
CVisualizationManager g_visuals;
CLiquidityEngine g_liquidity;
CSMTDetectionEngine g_smt;
CCorrelationEngine g_correlation;
CDisplacementEngine g_displacement;
CMarketStructureEngine g_structure;
CPremiumDiscountEngine g_premium_discount;
CFVGEngine g_fvg;
COrderBlockEngine g_order_block;
CMarketRegimeEngine g_regime;
CScoringEngine g_scoring;

MEMO_LiquidityMap g_map_a;
MEMO_LiquidityMap g_map_b;
MEMO_SetupContext g_last_context;
datetime g_last_bar_time = 0;
string g_status = "Initializing";

bool IsMetalsPair(const string a, const string b)
{
   const bool a_gold = StringFind(a, "XAUUSD") >= 0;
   const bool a_silver = StringFind(a, "XAGUSD") >= 0;
   const bool b_gold = StringFind(b, "XAUUSD") >= 0;
   const bool b_silver = StringFind(b, "XAGUSD") >= 0;
   return (a_gold && b_silver) || (a_silver && b_gold);
}

void LoadSettings()
{
   g_settings.symbol_a = InpSymbolA;
   g_settings.symbol_b = InpSymbolB;
   g_settings.magic_number = InpMagicNumber;
   g_settings.allow_live_trading = InpAllowLiveTrading;
   g_settings.debug_mode = InpDebugMode;
   g_settings.enable_visuals = InpEnableVisuals;
   g_settings.timer_seconds = InpTimerSeconds;

   g_settings.execution_tf = InpExecutionTF;
   g_settings.structure_tf = InpStructureTF;
   g_settings.correlation_tf = InpCorrelationTF;
   g_settings.analysis_bars = InpAnalysisBars;

   g_settings.asia_start_minute = MEMO_ParseHHMM(InpAsiaStart, 0);
   g_settings.asia_end_minute = MEMO_ParseHHMM(InpAsiaEnd, 360);
   g_settings.london_start_minute = MEMO_ParseHHMM(InpLondonStart, 420);
   g_settings.london_end_minute = MEMO_ParseHHMM(InpLondonEnd, 660);
   g_settings.newyork_start_minute = MEMO_ParseHHMM(InpNewYorkStart, 810);
   g_settings.newyork_end_minute = MEMO_ParseHHMM(InpNewYorkEnd, 1020);
   g_settings.ny_opening_range_minutes = InpNYOpeningRangeMinutes;
   g_settings.trade_asia = InpTradeAsia;
   g_settings.trade_london = InpTradeLondon;
   g_settings.trade_newyork = InpTradeNewYork;

   g_settings.sweep_lookback_bars = InpSweepLookbackBars;
   g_settings.sweep_buffer_points = InpSweepBufferPoints;
   g_settings.equal_level_tolerance_points = InpEqualLevelTolerancePoints;
   g_settings.correlation_lookback = InpCorrelationLookback;
   g_settings.minimum_correlation = InpMinimumCorrelation;

   g_settings.atr_period = InpATRPeriod;
   g_settings.minimum_displacement_points = InpMinimumDisplacementPoints;
   g_settings.displacement_atr_multiple = InpDisplacementATRMultiple;
   g_settings.minimum_body_ratio = InpMinimumBodyRatio;
   g_settings.consecutive_imbalance_candles = InpConsecutiveImbalanceCandles;
   g_settings.structure_lookback_bars = InpStructureLookbackBars;
   g_settings.swing_depth = InpSwingDepth;

   g_settings.minimum_fvg_points = InpMinimumFVGPoints;
   g_settings.maximum_fvg_points = InpMaximumFVGPoints;
   g_settings.entry_sensitivity_points = InpEntrySensitivityPoints;
   g_settings.order_block_lookback_bars = InpOrderBlockLookbackBars;

   g_settings.confidence_threshold = InpConfidenceThreshold;
   g_settings.enable_range_smt = InpEnableRangeSMT;
   g_settings.enable_trend_smt = InpEnableTrendSMT;
   g_settings.enable_expansion_smt = InpEnableExpansionSMT;
   g_settings.enable_reversal_smt = InpEnableReversalSMT;

   g_settings.use_dynamic_risk = InpUseDynamicRisk;
   g_settings.use_fixed_lots = InpUseFixedLots;
   g_settings.fixed_lots = InpFixedLots;
   g_settings.base_risk_percent = InpBaseRiskPercent;
   g_settings.risk_score_70_79 = InpRiskScore70To79;
   g_settings.risk_score_80_89 = InpRiskScore80To89;
   g_settings.risk_score_90_plus = InpRiskScore90Plus;
   g_settings.daily_drawdown_limit_percent = InpDailyDrawdownLimitPercent;
   g_settings.weekly_drawdown_limit_percent = InpWeeklyDrawdownLimitPercent;
   g_settings.session_drawdown_limit_percent = InpSessionDrawdownLimitPercent;
   g_settings.max_trades_per_day = InpMaxTradesPerDay;
   g_settings.max_trades_per_session = InpMaxTradesPerSession;
   g_settings.max_daily_losses = InpMaxDailyLosses;
   g_settings.max_session_losses = InpMaxSessionLosses;
   g_settings.consecutive_loss_limit = InpConsecutiveLossLimit;

   g_settings.enable_break_even = InpEnableBreakEven;
   g_settings.break_even_r_multiple = InpBreakEvenRMultiple;
   g_settings.break_even_lock_points = InpBreakEvenLockPoints;
   g_settings.enable_partial_take_profit = InpEnablePartialTakeProfit;
   g_settings.partial_close_percent = InpPartialClosePercent;
   g_settings.tp1_r_multiple = InpTP1RMultiple;
   g_settings.tp2_r_multiple = InpTP2RMultiple;
   g_settings.enable_atr_trailing = InpEnableATRTrailing;
   g_settings.atr_trailing_multiple = InpATRTrailingMultiple;
   g_settings.enable_structure_trailing = InpEnableStructureTrailing;
   g_settings.enable_fvg_trailing = InpEnableFVGTrailing;

   g_settings.enable_news_filter = InpEnableNewsFilter;
   g_settings.news_blackout_file = InpNewsBlackoutFile;
   g_settings.block_high_impact_news = InpBlockHighImpactNews;
   g_settings.block_medium_impact_news = InpBlockMediumImpactNews;
   g_settings.news_minutes_before = InpNewsMinutesBefore;
   g_settings.news_minutes_after = InpNewsMinutesAfter;

   g_settings.panel_corner = InpPanelCorner;
   g_settings.buy_color = InpBuyColor;
   g_settings.sell_color = InpSellColor;
   g_settings.neutral_color = InpNeutralColor;
   g_settings.Normalize();
}

bool BuildCandidateContext(MEMO_SetupContext &context)
{
   context.Reset();
   context.session = g_sessions.CurrentSession(TimeCurrent());

   string reason = "";
   if(!g_sessions.CanTradeNow(TimeCurrent(), reason))
   {
      context.rejection_reason = reason;
      g_status = reason;
      return false;
   }

   if(!g_liquidity.Update(g_settings.symbol_a, g_map_a) || !g_liquidity.Update(g_settings.symbol_b, g_map_b))
   {
      context.rejection_reason = "Liquidity maps unavailable";
      g_status = context.rejection_reason;
      return false;
   }

   g_visuals.DrawLiquidity(g_map_a);
   g_visuals.DrawLiquidity(g_map_b);

   if(!g_smt.Detect(g_settings.symbol_a, g_settings.symbol_b, g_map_a, g_map_b, context.smt))
   {
      context.rejection_reason = "No valid SMT";
      g_status = context.rejection_reason;
      return false;
   }

   context.symbol = context.smt.candidate_symbol;
   context.direction = context.smt.direction;
   context.valid = true;

   context.liquidity.valid = true;
   context.liquidity.symbol = context.smt.swept_symbol;
   context.liquidity.direction = context.smt.direction;
   context.liquidity.tier = context.smt.tier;
   context.liquidity.level_name = context.smt.source_level;
   context.liquidity.level_price = context.smt.source_price;
   context.liquidity.event_time = context.smt.event_time;
   context.liquidity.sweep_extreme = context.smt.source_price;

   if(!g_correlation.IsValid(g_settings.symbol_a, g_settings.symbol_b, context.correlation, reason))
   {
      context.rejection_reason = reason;
      g_status = reason;
      return false;
   }

   if(g_news.IsBlocked(context.symbol, TimeCurrent(), reason))
   {
      context.rejection_reason = reason;
      g_status = reason;
      g_log.Decision("NewsFilter", context.symbol, "News", "REJECT", 0.0, reason);
      return false;
   }

   if(!g_regime.Detect(context.symbol, context.regime) || !g_regime.IsAllowed(context.regime, reason))
   {
      context.rejection_reason = reason;
      g_status = reason;
      g_log.Decision("MarketRegimeEngine", context.symbol, "Regime", "REJECT", 0.0, reason);
      return false;
   }

   if(!g_displacement.Detect(context.symbol, context.direction, context.displacement))
   {
      context.rejection_reason = "No displacement confirmation";
      g_status = context.rejection_reason;
      return false;
   }

   if(!g_structure.Detect(context.symbol, context.direction, context.structure))
   {
      context.rejection_reason = "No MSS/CHOCH";
      g_status = context.rejection_reason;
      return false;
   }

   bool pd_ok = false;
   if(context.symbol == g_settings.symbol_a)
      pd_ok = g_premium_discount.Validate(context.symbol, g_map_a, context.direction, reason);
   else if(context.symbol == g_settings.symbol_b)
      pd_ok = g_premium_discount.Validate(context.symbol, g_map_b, context.direction, reason);
   else
   {
      context.rejection_reason = "Candidate map unavailable";
      g_status = context.rejection_reason;
      return false;
   }

   if(!pd_ok)
   {
      context.rejection_reason = reason;
      g_status = reason;
      return false;
   }

   const bool fvg_found = g_fvg.DetectRecent(context.symbol, context.direction, context.fvg);
   const bool ob_found = g_order_block.DetectRecent(context.symbol, context.direction, context.order_block);
   const bool fvg_retest = fvg_found && g_fvg.IsRetested(context.symbol, context.fvg);
   const bool ob_retest = ob_found && g_order_block.IsRetested(context.symbol, context.order_block);

   if(!fvg_retest && !ob_retest)
   {
      context.rejection_reason = "No FVG/order-block retest";
      g_status = context.rejection_reason;
      return false;
   }

   const bool session_aligned = g_sessions.IsMajorLiquidityWindow(TimeCurrent());
   g_scoring.Calculate(context, pd_ok, fvg_retest, ob_retest, session_aligned,
                       g_correlation.Score(context.correlation), g_regime.Score(context.regime));

   if(!g_scoring.Passes(context, reason))
   {
      context.rejection_reason = reason;
      g_status = reason;
      return false;
   }

   if(!g_trade.BuildStops(context))
   {
      context.rejection_reason = "Unable to build valid stops";
      g_status = context.rejection_reason;
      return false;
   }

   return true;
}

void ProcessSetup()
{
   MEMO_SetupContext context;
   if(!BuildCandidateContext(context))
   {
      g_last_context = context;
      g_stats.RecordSetup(context, "REJECT: " + context.rejection_reason);
      return;
   }

   string reason = "";
   g_risk.UpdateBaselines(context.session);
   if(!g_risk.CanTrade(context, reason))
   {
      context.rejection_reason = reason;
      g_last_context = context;
      g_status = reason;
      g_log.Decision("RiskManager", context.symbol, "Risk", "REJECT", context.score.total, reason);
      g_stats.RecordSetup(context, "REJECT: " + reason);
      return;
   }

   const double lots = g_risk.CalculateLots(context.symbol, context.entry_price, context.stop_loss, context.score.total);
   const bool executed = g_trade.Execute(context, lots);
   g_status = executed ? "Trade executed" : "Execution rejected";
   g_last_context = context;
   g_stats.RecordSetup(context, executed ? "EXECUTED" : "REJECT: execution failed");
   g_visuals.DrawSetup(context);
}

int OnInit()
{
   LoadSettings();

   if(!IsMetalsPair(g_settings.symbol_a, g_settings.symbol_b))
   {
      Print("[MEMO][ERROR] This EA is restricted to the XAUUSD/XAGUSD pair.");
      return INIT_PARAMETERS_INCORRECT;
   }

   if(!g_log.Init("MEMO_SMT_decision_log.csv", g_settings.debug_mode))
      return INIT_FAILED;

   if(!g_symbols.Init(g_settings, &g_log))
      return INIT_FAILED;

   g_sessions.Init(g_settings);
   g_news.Init(g_settings, &g_log);
   g_risk.Init(g_settings, &g_log);
   g_trade.Init(g_settings, &g_log);
   g_stats.Init(g_settings, &g_log);
   g_visuals.Init(g_settings);

   g_liquidity.Init(g_settings, &g_log, &g_sessions);
   g_smt.Init(g_settings, &g_liquidity, &g_log);
   g_correlation.Init(g_settings, &g_log);
   g_displacement.Init(g_settings, &g_log);
   g_structure.Init(g_settings, &g_log);
   g_premium_discount.Init(&g_log);
   g_fvg.Init(g_settings, &g_log);
   g_order_block.Init(g_settings, &g_log);
   g_regime.Init(g_settings, &g_log);
   g_scoring.Init(g_settings, &g_log);

   g_map_a.Reset(g_settings.symbol_a);
   g_map_b.Reset(g_settings.symbol_b);
   g_last_context.Reset();

   EventSetTimer(g_settings.timer_seconds);
   g_status = "Online";
   g_log.Info("MEMO", "XAU/XAG SMT EA online");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   EventKillTimer();
   g_visuals.Clear();
   g_stats.Close();
   g_log.Info("MEMO", "EA deinitialized reason=" + IntegerToString(reason));
   g_log.Close();
}

void OnTick()
{
   g_trade.ManageOpenPositions();
   g_stats.Update();

   const datetime bar_time = iTime(g_settings.symbol_a, g_settings.execution_tf, 0);
   if(bar_time == 0 || bar_time == g_last_bar_time)
      return;

   g_last_bar_time = bar_time;
   ProcessSetup();
   g_visuals.UpdatePanel(g_last_context, g_stats.Summary(), g_status);
}

void OnTimer()
{
   g_trade.ManageOpenPositions();
   g_stats.Update();
   g_risk.UpdateBaselines(g_sessions.CurrentSession(TimeCurrent()));
   g_visuals.UpdatePanel(g_last_context, g_stats.Summary(), g_status);
}
