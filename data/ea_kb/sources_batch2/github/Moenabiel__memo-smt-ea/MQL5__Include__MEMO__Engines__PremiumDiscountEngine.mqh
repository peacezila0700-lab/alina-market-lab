#ifndef MEMO_ENGINES_PREMIUM_DISCOUNT_ENGINE_MQH
#define MEMO_ENGINES_PREMIUM_DISCOUNT_ENGINE_MQH

#include <MEMO\Core\Settings.mqh>
#include <MEMO\Core\MarketData.mqh>
#include <MEMO\Managers\LoggingManager.mqh>

class CPremiumDiscountEngine
{
private:
   CLoggingManager *m_log;

   MEMO_PriceRange SelectRange(const MEMO_LiquidityMap &map) const
   {
      if(map.newyork.valid && map.newyork.Size() > 0.0)
         return map.newyork;
      if(map.london.valid && map.london.Size() > 0.0)
         return map.london;
      if(map.asia.valid && map.asia.Size() > 0.0)
         return map.asia;
      if(map.previous_day.valid && map.previous_day.Size() > 0.0)
         return map.previous_day;
      return map.previous_week;
   }

public:
   CPremiumDiscountEngine()
   {
      m_log = NULL;
   }

   void Init(CLoggingManager *logger)
   {
      m_log = logger;
   }

   bool Validate(const string symbol,
                 const MEMO_LiquidityMap &map,
                 const MEMO_Direction direction,
                 string &reason) const
   {
      const MEMO_PriceRange range = SelectRange(map);
      if(!range.valid)
      {
         reason = "No dealing range available";
         return false;
      }

      const double price = MEMO_MidPrice(symbol);
      const double midpoint = range.Midpoint();

      const bool valid = (direction == MEMO_DIR_BUY && price <= midpoint)
                      || (direction == MEMO_DIR_SELL && price >= midpoint);

      reason = range.name
             + " price=" + DoubleToString(price, 2)
             + " midpoint=" + DoubleToString(midpoint, 2)
             + " zone=" + (price < midpoint ? "discount" : (price > midpoint ? "premium" : "equilibrium"));

      if(m_log != NULL)
         m_log.Decision("PremiumDiscountEngine", symbol, "PremiumDiscount", valid ? "ACCEPT" : "REJECT", valid ? 10.0 : 0.0, reason);

      return valid;
   }
};

#endif
