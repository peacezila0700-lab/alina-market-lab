#ifndef MEMO_MANAGERS_RISK_MANAGER_MQH
#define MEMO_MANAGERS_RISK_MANAGER_MQH

#include <MEMO\Core\Settings.mqh>
#include <MEMO\Core\MarketData.mqh>
#include <MEMO\Managers\LoggingManager.mqh>

class CRiskManager
{
private:
   MEMO_Settings m_settings;
   CLoggingManager *m_log;
   datetime m_day_start;
   datetime m_week_start;
   datetime m_session_start;
   MEMO_SessionId m_session;
   double m_day_start_equity;
   double m_week_start_equity;
   double m_session_start_equity;
   bool m_emergency_pause;

   datetime WeekStart(const datetime now) const
   {
      MqlDateTime dt;
      TimeToStruct(now, dt);
      int days_back = dt.day_of_week == 0 ? 6 : dt.day_of_week - 1;
      return MEMO_StartOfDay(now) - days_back * 86400;
   }

   double ClosedProfitSince(const datetime start_time) const
   {
      if(!HistorySelect(start_time, TimeCurrent()))
         return 0.0;

      double profit = 0.0;
      const int total = HistoryDealsTotal();
      for(int i = 0; i < total; i++)
      {
         const ulong ticket = HistoryDealGetTicket(i);
         if(ticket == 0)
            continue;
         if((long)HistoryDealGetInteger(ticket, DEAL_MAGIC) != m_settings.magic_number)
            continue;

         const long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
         if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_INOUT)
            continue;

         profit += HistoryDealGetDouble(ticket, DEAL_PROFIT)
                 + HistoryDealGetDouble(ticket, DEAL_SWAP)
                 + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
      }
      return profit;
   }

   int ClosedLossesSince(const datetime start_time) const
   {
      if(!HistorySelect(start_time, TimeCurrent()))
         return 0;

      int losses = 0;
      const int total = HistoryDealsTotal();
      for(int i = 0; i < total; i++)
      {
         const ulong ticket = HistoryDealGetTicket(i);
         if(ticket == 0)
            continue;
         if((long)HistoryDealGetInteger(ticket, DEAL_MAGIC) != m_settings.magic_number)
            continue;

         const long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
         if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_INOUT)
            continue;

         const double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT)
                             + HistoryDealGetDouble(ticket, DEAL_SWAP)
                             + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         if(profit < 0.0)
            losses++;
      }
      return losses;
   }

   int EntriesSince(const datetime start_time) const
   {
      if(!HistorySelect(start_time, TimeCurrent()))
         return 0;

      int entries = 0;
      const int total = HistoryDealsTotal();
      for(int i = 0; i < total; i++)
      {
         const ulong ticket = HistoryDealGetTicket(i);
         if(ticket == 0)
            continue;
         if((long)HistoryDealGetInteger(ticket, DEAL_MAGIC) != m_settings.magic_number)
            continue;

         const long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
         if(entry == DEAL_ENTRY_IN || entry == DEAL_ENTRY_INOUT)
            entries++;
      }
      return entries;
   }

   int ConsecutiveLosses() const
   {
      if(!HistorySelect(m_week_start, TimeCurrent()))
         return 0;

      int losses = 0;
      for(int i = HistoryDealsTotal() - 1; i >= 0; i--)
      {
         const ulong ticket = HistoryDealGetTicket(i);
         if(ticket == 0)
            continue;
         if((long)HistoryDealGetInteger(ticket, DEAL_MAGIC) != m_settings.magic_number)
            continue;

         const long entry = HistoryDealGetInteger(ticket, DEAL_ENTRY);
         if(entry != DEAL_ENTRY_OUT && entry != DEAL_ENTRY_INOUT)
            continue;

         const double profit = HistoryDealGetDouble(ticket, DEAL_PROFIT)
                             + HistoryDealGetDouble(ticket, DEAL_SWAP)
                             + HistoryDealGetDouble(ticket, DEAL_COMMISSION);
         if(profit < 0.0)
            losses++;
         else
            break;
      }
      return losses;
   }

public:
   CRiskManager()
   {
      m_log = NULL;
      m_day_start = 0;
      m_week_start = 0;
      m_session_start = 0;
      m_session = MEMO_SESSION_NONE;
      m_day_start_equity = 0.0;
      m_week_start_equity = 0.0;
      m_session_start_equity = 0.0;
      m_emergency_pause = false;
   }

   void Init(const MEMO_Settings &settings, CLoggingManager *logger)
   {
      m_settings = settings;
      m_log = logger;
      const datetime now = TimeCurrent();
      m_day_start = MEMO_StartOfDay(now);
      m_week_start = WeekStart(now);
      m_session_start = now;
      m_day_start_equity = AccountInfoDouble(ACCOUNT_EQUITY);
      m_week_start_equity = m_day_start_equity;
      m_session_start_equity = m_day_start_equity;
      m_emergency_pause = false;
   }

   void UpdateBaselines(const MEMO_SessionId current_session)
   {
      const datetime now = TimeCurrent();
      const datetime current_day = MEMO_StartOfDay(now);
      const datetime current_week = WeekStart(now);

      if(current_day != m_day_start)
      {
         m_day_start = current_day;
         m_day_start_equity = AccountInfoDouble(ACCOUNT_EQUITY);
      }

      if(current_week != m_week_start)
      {
         m_week_start = current_week;
         m_week_start_equity = AccountInfoDouble(ACCOUNT_EQUITY);
      }

      if(current_session != m_session)
      {
         m_session = current_session;
         m_session_start = now;
         m_session_start_equity = AccountInfoDouble(ACCOUNT_EQUITY);
      }
   }

   void EmergencyPause(const bool paused)
   {
      m_emergency_pause = paused;
   }

   double RiskPercentForScore(const int score) const
   {
      if(!m_settings.use_dynamic_risk)
         return m_settings.base_risk_percent;
      if(score >= 90)
         return m_settings.risk_score_90_plus;
      if(score >= 80)
         return m_settings.risk_score_80_89;
      if(score >= 70)
         return m_settings.risk_score_70_79;
      return m_settings.base_risk_percent * 0.5;
   }

   double CalculateLots(const string symbol,
                        const double entry,
                        const double stop_loss,
                        const int score) const
   {
      if(m_settings.use_fixed_lots)
         return MEMO_NormalizeVolume(symbol, m_settings.fixed_lots);

      const double distance = MathAbs(entry - stop_loss);
      const double tick_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
      const double tick_value = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
      if(distance <= 0.0 || tick_size <= 0.0 || tick_value <= 0.0)
         return 0.0;

      const double risk_money = AccountInfoDouble(ACCOUNT_EQUITY) * RiskPercentForScore(score) / 100.0;
      const double loss_per_lot = (distance / tick_size) * tick_value;
      if(loss_per_lot <= 0.0)
         return 0.0;

      return MEMO_NormalizeVolume(symbol, risk_money / loss_per_lot);
   }

   bool CanTrade(const MEMO_SetupContext &context, string &reason) const
   {
      if(!m_settings.allow_live_trading)
      {
         reason = "Live trading disabled by input";
         return false;
      }

      if(m_emergency_pause)
      {
         reason = "Emergency pause active";
         return false;
      }

      if(!TerminalInfoInteger(TERMINAL_TRADE_ALLOWED) || !MQLInfoInteger(MQL_TRADE_ALLOWED))
      {
         reason = "Terminal or EA trading permission disabled";
         return false;
      }

      const double daily_profit = ClosedProfitSince(m_day_start);
      const double weekly_profit = ClosedProfitSince(m_week_start);
      const double session_profit = ClosedProfitSince(m_session_start);

      const double daily_dd = m_day_start_equity > 0.0 ? -daily_profit / m_day_start_equity * 100.0 : 0.0;
      const double weekly_dd = m_week_start_equity > 0.0 ? -weekly_profit / m_week_start_equity * 100.0 : 0.0;
      const double session_dd = m_session_start_equity > 0.0 ? -session_profit / m_session_start_equity * 100.0 : 0.0;

      if(daily_dd >= m_settings.daily_drawdown_limit_percent)
      {
         reason = "Daily drawdown limit reached";
         return false;
      }
      if(weekly_dd >= m_settings.weekly_drawdown_limit_percent)
      {
         reason = "Weekly drawdown limit reached";
         return false;
      }
      if(session_dd >= m_settings.session_drawdown_limit_percent)
      {
         reason = "Session drawdown limit reached";
         return false;
      }

      if(EntriesSince(m_day_start) >= m_settings.max_trades_per_day)
      {
         reason = "Maximum daily trades reached";
         return false;
      }

      if(EntriesSince(m_session_start) >= m_settings.max_trades_per_session)
      {
         reason = "Maximum session trades reached";
         return false;
      }

      if(ClosedLossesSince(m_day_start) >= m_settings.max_daily_losses)
      {
         reason = "Maximum daily losses reached";
         return false;
      }

      if(ClosedLossesSince(m_session_start) >= m_settings.max_session_losses)
      {
         reason = "Maximum session losses reached";
         return false;
      }

      if(ConsecutiveLosses() >= m_settings.consecutive_loss_limit)
      {
         reason = "Consecutive loss shutdown active";
         return false;
      }

      reason = "Risk checks passed";
      return true;
   }
};

#endif
