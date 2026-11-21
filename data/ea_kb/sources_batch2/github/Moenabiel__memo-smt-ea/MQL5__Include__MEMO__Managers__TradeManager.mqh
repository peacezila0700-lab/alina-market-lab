#ifndef MEMO_MANAGERS_TRADE_MANAGER_MQH
#define MEMO_MANAGERS_TRADE_MANAGER_MQH

#include <Trade\Trade.mqh>
#include <MEMO\Core\Settings.mqh>
#include <MEMO\Core\MarketData.mqh>
#include <MEMO\Managers\LoggingManager.mqh>

class CTradeManager
{
private:
   MEMO_Settings m_settings;
   CLoggingManager *m_log;
   CTrade m_trade;

   bool IsManagedPositionSelected() const
   {
      return (long)PositionGetInteger(POSITION_MAGIC) == m_settings.magic_number;
   }

   string PartialKey(const ulong ticket) const
   {
      return "MEMO_PARTIAL_" + IntegerToString((long)ticket);
   }

   double RecentStructureStop(const string symbol, const ENUM_POSITION_TYPE type) const
   {
      MqlRates rates[];
      if(!MEMO_CopyRatesSeries(symbol, m_settings.structure_tf, 0, 40, rates))
         return 0.0;

      if(type == POSITION_TYPE_BUY)
      {
         double low = rates[2].low;
         for(int i = 2; i < MathMin(20, ArraySize(rates)); i++)
            low = MathMin(low, rates[i].low);
         return low;
      }

      if(type == POSITION_TYPE_SELL)
      {
         double high = rates[2].high;
         for(int i = 2; i < MathMin(20, ArraySize(rates)); i++)
            high = MathMax(high, rates[i].high);
         return high;
      }

      return 0.0;
   }

   double RecentFVGTrailStop(const string symbol, const ENUM_POSITION_TYPE type) const
   {
      MqlRates rates[];
      if(!MEMO_CopyRatesSeries(symbol, m_settings.execution_tf, 0, 30, rates))
         return 0.0;

      if(type == POSITION_TYPE_BUY)
      {
         for(int i = 1; i + 2 < ArraySize(rates); i++)
         {
            if(rates[i + 2].high < rates[i].low)
               return rates[i + 2].high;
         }
      }
      else if(type == POSITION_TYPE_SELL)
      {
         for(int i = 1; i + 2 < ArraySize(rates); i++)
         {
            if(rates[i + 2].low > rates[i].high)
               return rates[i + 2].low;
         }
      }

      return 0.0;
   }

   void TightenStop(const string symbol, const ENUM_POSITION_TYPE type, double candidate_sl)
   {
      if(candidate_sl <= 0.0)
         return;

      const double current_sl = PositionGetDouble(POSITION_SL);
      const double tp = PositionGetDouble(POSITION_TP);
      const double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      const double min_distance = (double)SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL) * point;
      const double bid = MEMO_Bid(symbol);
      const double ask = MEMO_Ask(symbol);

      if(type == POSITION_TYPE_BUY)
      {
         candidate_sl = MEMO_NormalizePrice(symbol, candidate_sl);
         if(candidate_sl <= current_sl || candidate_sl >= bid - min_distance)
            return;
      }
      else if(type == POSITION_TYPE_SELL)
      {
         candidate_sl = MEMO_NormalizePrice(symbol, candidate_sl);
         if((current_sl > 0.0 && candidate_sl >= current_sl) || candidate_sl <= ask + min_distance)
            return;
      }

      if(m_trade.PositionModify(symbol, candidate_sl, tp) && m_log != NULL)
         m_log.Decision("TradeManager", symbol, "Trailing", "ACCEPT", 0.0, "Stop tightened to " + DoubleToString(candidate_sl, 2));
   }

public:
   CTradeManager()
   {
      m_log = NULL;
   }

   void Init(const MEMO_Settings &settings, CLoggingManager *logger)
   {
      m_settings = settings;
      m_log = logger;
      m_trade.SetExpertMagicNumber(m_settings.magic_number);
      m_trade.SetDeviationInPoints(20);
   }

   bool HasOpenPosition(const string symbol) const
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         const ulong ticket = PositionGetTicket(i);
         if(ticket == 0)
            continue;
         if(PositionGetString(POSITION_SYMBOL) == symbol && IsManagedPositionSelected())
            return true;
      }
      return false;
   }

   bool BuildStops(MEMO_SetupContext &context) const
   {
      const string symbol = context.symbol;
      const double point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      if(point <= 0.0)
         return false;

      context.entry_price = context.direction == MEMO_DIR_BUY ? MEMO_Ask(symbol) : MEMO_Bid(symbol);
      const double atr_points = MEMO_ATRPoints(symbol, m_settings.execution_tf, m_settings.atr_period, 1);
      const double buffer = MathMax(m_settings.sweep_buffer_points, atr_points * 0.20) * point;

      if(context.direction == MEMO_DIR_BUY)
      {
         double stop = context.entry_price - MathMax(atr_points, 100.0) * point;
         if(context.liquidity.valid)
            stop = MathMin(stop, context.liquidity.sweep_extreme - buffer);
         if(context.fvg.valid)
            stop = MathMin(stop, context.fvg.lower - buffer);
         if(context.order_block.valid)
            stop = MathMin(stop, context.order_block.lower - buffer);

         context.stop_loss = MEMO_NormalizePrice(symbol, stop);
         const double risk = context.entry_price - context.stop_loss;
         if(risk <= 0.0)
            return false;
         context.take_profit_1 = MEMO_NormalizePrice(symbol, context.entry_price + risk * m_settings.tp1_r_multiple);
         context.take_profit_2 = MEMO_NormalizePrice(symbol, context.entry_price + risk * m_settings.tp2_r_multiple);
         return true;
      }

      if(context.direction == MEMO_DIR_SELL)
      {
         double stop = context.entry_price + MathMax(atr_points, 100.0) * point;
         if(context.liquidity.valid)
            stop = MathMax(stop, context.liquidity.sweep_extreme + buffer);
         if(context.fvg.valid)
            stop = MathMax(stop, context.fvg.upper + buffer);
         if(context.order_block.valid)
            stop = MathMax(stop, context.order_block.upper + buffer);

         context.stop_loss = MEMO_NormalizePrice(symbol, stop);
         const double risk = context.stop_loss - context.entry_price;
         if(risk <= 0.0)
            return false;
         context.take_profit_1 = MEMO_NormalizePrice(symbol, context.entry_price - risk * m_settings.tp1_r_multiple);
         context.take_profit_2 = MEMO_NormalizePrice(symbol, context.entry_price - risk * m_settings.tp2_r_multiple);
         return true;
      }

      return false;
   }

   bool Execute(const MEMO_SetupContext &context, const double lots)
   {
      if(lots <= 0.0)
      {
         if(m_log != NULL)
            m_log.Decision("TradeManager", context.symbol, "Execution", "REJECT", context.score.total, "Calculated lots <= 0");
         return false;
      }

      if(HasOpenPosition(context.symbol))
      {
         if(m_log != NULL)
            m_log.Decision("TradeManager", context.symbol, "Execution", "REJECT", context.score.total, "Managed position already open");
         return false;
      }

      const string comment = "MEMO SMT " + MEMO_TierText(context.smt.tier) + " score " + IntegerToString(context.score.total);
      bool ok = false;

      if(context.direction == MEMO_DIR_BUY)
         ok = m_trade.Buy(lots, context.symbol, 0.0, context.stop_loss, context.take_profit_2, comment);
      else if(context.direction == MEMO_DIR_SELL)
         ok = m_trade.Sell(lots, context.symbol, 0.0, context.stop_loss, context.take_profit_2, comment);

      if(m_log != NULL)
      {
         m_log.Decision("TradeManager", context.symbol, "Execution", ok ? "ACCEPT" : "REJECT", context.score.total,
                        ok ? "Order sent lots=" + DoubleToString(lots, 2)
                           : "Order failed retcode=" + IntegerToString((int)m_trade.ResultRetcode()) + " " + m_trade.ResultRetcodeDescription());
      }

      return ok;
   }

   void ManageOpenPositions()
   {
      for(int i = PositionsTotal() - 1; i >= 0; i--)
      {
         const ulong ticket = PositionGetTicket(i);
         if(ticket == 0)
            continue;
         if(!IsManagedPositionSelected())
            continue;

         const string symbol = PositionGetString(POSITION_SYMBOL);
         const ENUM_POSITION_TYPE type = (ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
         const double open_price = PositionGetDouble(POSITION_PRICE_OPEN);
         const double sl = PositionGetDouble(POSITION_SL);
         const double tp = PositionGetDouble(POSITION_TP);
         const double volume = PositionGetDouble(POSITION_VOLUME);
         const double bid = MEMO_Bid(symbol);
         const double ask = MEMO_Ask(symbol);
         const double point = SymbolInfoDouble(symbol, SYMBOL_POINT);

         if(point <= 0.0 || sl <= 0.0)
            continue;

         const double current = type == POSITION_TYPE_BUY ? bid : ask;
         const double risk = MathAbs(open_price - sl);
         if(risk <= 0.0)
            continue;

         const double r_multiple = type == POSITION_TYPE_BUY
                                 ? (current - open_price) / risk
                                 : (open_price - current) / risk;

         if(m_settings.enable_partial_take_profit && r_multiple >= m_settings.tp1_r_multiple && !GlobalVariableCheck(PartialKey(ticket)))
         {
            const double close_volume = MEMO_NormalizeVolume(symbol, volume * m_settings.partial_close_percent / 100.0);
            if(close_volume > 0.0 && close_volume < volume && m_trade.PositionClosePartial(symbol, close_volume))
               GlobalVariableSet(PartialKey(ticket), TimeCurrent());
         }

         if(m_settings.enable_break_even && r_multiple >= m_settings.break_even_r_multiple)
         {
            double be_sl = open_price;
            if(type == POSITION_TYPE_BUY)
               be_sl += m_settings.break_even_lock_points * point;
            else
               be_sl -= m_settings.break_even_lock_points * point;
            TightenStop(symbol, type, be_sl);
         }

         if(m_settings.enable_atr_trailing)
         {
            const double atr_points = MEMO_ATRPoints(symbol, m_settings.execution_tf, m_settings.atr_period, 1);
            if(type == POSITION_TYPE_BUY)
               TightenStop(symbol, type, bid - atr_points * m_settings.atr_trailing_multiple * point);
            else if(type == POSITION_TYPE_SELL)
               TightenStop(symbol, type, ask + atr_points * m_settings.atr_trailing_multiple * point);
         }

         if(m_settings.enable_structure_trailing)
            TightenStop(symbol, type, RecentStructureStop(symbol, type));

         if(m_settings.enable_fvg_trailing)
            TightenStop(symbol, type, RecentFVGTrailStop(symbol, type));

         if(tp <= 0.0 && m_log != NULL)
            m_log.Debug("TradeManager", symbol + " position has no TP");
      }
   }
};

#endif
