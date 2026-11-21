#ifndef MEMO_MANAGERS_SYMBOL_MANAGER_MQH
#define MEMO_MANAGERS_SYMBOL_MANAGER_MQH

#include <MEMO\Core\Settings.mqh>
#include <MEMO\Managers\LoggingManager.mqh>

class CSymbolManager
{
private:
   MEMO_SymbolSpec m_a;
   MEMO_SymbolSpec m_b;
   CLoggingManager *m_log;

   bool LoadSpec(const string symbol, MEMO_SymbolSpec &spec)
   {
      spec.Reset();
      spec.symbol = symbol;

      if(symbol == "")
         return false;

      if(!SymbolSelect(symbol, true))
      {
         if(m_log != NULL)
            m_log.Error("SymbolManager", "Unable to select symbol: " + symbol);
         return false;
      }

      spec.digits = (int)SymbolInfoInteger(symbol, SYMBOL_DIGITS);
      spec.point = SymbolInfoDouble(symbol, SYMBOL_POINT);
      spec.tick_size = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_SIZE);
      spec.tick_value = SymbolInfoDouble(symbol, SYMBOL_TRADE_TICK_VALUE);
      spec.volume_min = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MIN);
      spec.volume_max = SymbolInfoDouble(symbol, SYMBOL_VOLUME_MAX);
      spec.volume_step = SymbolInfoDouble(symbol, SYMBOL_VOLUME_STEP);
      spec.stops_level_points = (double)SymbolInfoInteger(symbol, SYMBOL_TRADE_STOPS_LEVEL);
      spec.freeze_level_points = (double)SymbolInfoInteger(symbol, SYMBOL_TRADE_FREEZE_LEVEL);
      spec.ready = spec.point > 0.0 && spec.tick_size > 0.0 && spec.volume_step > 0.0;

      if(!spec.ready && m_log != NULL)
         m_log.Error("SymbolManager", "Incomplete broker metadata for " + symbol);

      return spec.ready;
   }

public:
   CSymbolManager()
   {
      m_log = NULL;
      m_a.Reset();
      m_b.Reset();
   }

   bool Init(const MEMO_Settings &settings, CLoggingManager *logger)
   {
      m_log = logger;
      const bool ok_a = LoadSpec(settings.symbol_a, m_a);
      const bool ok_b = LoadSpec(settings.symbol_b, m_b);

      if(ok_a && ok_b)
      {
         if(m_log != NULL)
            m_log.Info("SymbolManager", "Symbols online: " + m_a.symbol + " / " + m_b.symbol);
         return true;
      }

      return false;
   }

   bool IsManagedSymbol(const string symbol) const
   {
      return symbol == m_a.symbol || symbol == m_b.symbol;
   }

   string SymbolA() const
   {
      return m_a.symbol;
   }

   string SymbolB() const
   {
      return m_b.symbol;
   }

   string OtherSymbol(const string symbol) const
   {
      if(symbol == m_a.symbol)
         return m_b.symbol;
      if(symbol == m_b.symbol)
         return m_a.symbol;
      return "";
   }

   bool GetSpec(const string symbol, MEMO_SymbolSpec &spec) const
   {
      if(symbol == m_a.symbol)
      {
         spec = m_a;
         return true;
      }
      if(symbol == m_b.symbol)
      {
         spec = m_b;
         return true;
      }
      spec.Reset();
      return false;
   }

   double Point(const string symbol) const
   {
      if(symbol == m_a.symbol)
         return m_a.point;
      if(symbol == m_b.symbol)
         return m_b.point;
      return SymbolInfoDouble(symbol, SYMBOL_POINT);
   }
};

#endif
