#ifndef MEMO_MANAGERS_STATISTICS_MANAGER_MQH
#define MEMO_MANAGERS_STATISTICS_MANAGER_MQH

#include <MEMO\Core\Settings.mqh>
#include <MEMO\Managers\LoggingManager.mqh>

class CStatisticsManager
{
private:
   MEMO_Settings m_settings;
   CLoggingManager *m_log;
   int m_setup_handle;
   datetime m_last_update;
   int m_trades;
   int m_wins;
   int m_losses;
   double m_gross_profit;
   double m_gross_loss;
   double m_profit_factor;
   double m_win_rate;

public:
   CStatisticsManager()
   {
      m_log = NULL;
      m_setup_handle = INVALID_HANDLE;
      m_last_update = 0;
      m_trades = 0;
      m_wins = 0;
      m_losses = 0;
      m_gross_profit = 0.0;
      m_gross_loss = 0.0;
      m_profit_factor = 0.0;
      m_win_rate = 0.0;
   }

   bool Init(const MEMO_Settings &settings, CLoggingManager *logger)
   {
      m_settings = settings;
      m_log = logger;
      m_setup_handle = FileOpen("MEMO_SMT_setup_history.csv", FILE_READ | FILE_WRITE | FILE_CSV | FILE_ANSI | FILE_SHARE_READ, ';');
      if(m_setup_handle == INVALID_HANDLE)
         return false;

      if(FileSize(m_setup_handle) == 0)
         FileWrite(m_setup_handle,
                   "time", "symbol", "direction", "session", "tier", "regime", "correlation",
                   "score", "entry", "sl", "tp1", "tp2", "notes", "decision");

      FileSeek(m_setup_handle, 0, SEEK_END);
      Update();
      return true;
   }

   void Close()
   {
      if(m_setup_handle != INVALID_HANDLE)
      {
         FileClose(m_setup_handle);
         m_setup_handle = INVALID_HANDLE;
      }
   }

   void RecordSetup(const MEMO_SetupContext &context, const string decision)
   {
      if(m_setup_handle == INVALID_HANDLE)
         return;

      FileSeek(m_setup_handle, 0, SEEK_END);
      FileWrite(m_setup_handle,
                TimeToString(TimeCurrent(), TIME_DATE | TIME_SECONDS),
                context.symbol,
                MEMO_DirectionText(context.direction),
                MEMO_SessionText(context.session),
                MEMO_TierText(context.smt.tier),
                MEMO_RegimeText(context.regime.regime),
                DoubleToString(context.correlation, 4),
                IntegerToString(context.score.total),
                DoubleToString(context.entry_price, 2),
                DoubleToString(context.stop_loss, 2),
                DoubleToString(context.take_profit_1, 2),
                DoubleToString(context.take_profit_2, 2),
                context.score.notes,
                decision);
      FileFlush(m_setup_handle);
   }

   void Update()
   {
      if(TimeCurrent() - m_last_update < 30)
         return;

      m_last_update = TimeCurrent();
      m_trades = 0;
      m_wins = 0;
      m_losses = 0;
      m_gross_profit = 0.0;
      m_gross_loss = 0.0;

      const datetime from = TimeCurrent() - 86400 * 180;
      if(!HistorySelect(from, TimeCurrent()))
         return;

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

         m_trades++;
         if(profit >= 0.0)
         {
            m_wins++;
            m_gross_profit += profit;
         }
         else
         {
            m_losses++;
            m_gross_loss += MathAbs(profit);
         }
      }

      m_win_rate = m_trades > 0 ? (double)m_wins / (double)m_trades * 100.0 : 0.0;
      m_profit_factor = m_gross_loss > 0.0 ? m_gross_profit / m_gross_loss : (m_gross_profit > 0.0 ? 99.0 : 0.0);
   }

   string Summary() const
   {
      return "Trades " + IntegerToString(m_trades)
           + " | WR " + DoubleToString(m_win_rate, 1) + "%"
           + " | PF " + DoubleToString(m_profit_factor, 2);
   }
};

#endif
