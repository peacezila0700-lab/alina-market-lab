#include <Trade/Trade.mqh>

namespace FxcePositionMagic
{
   
   /**
     * @brief Get total positions with magic number.
     * 
     * @param magic_num value of Magic Number. 
     * @return Return total positions.  
     */
     
   int PositionsTotalByMagic(ulong magic_num)
   {
      int total=0;
      
      if(PositionsTotal()>0 && PositionSelect(_Symbol)){
         for(int i=0; i<PositionsTotal();i++){
            ulong position_ticket=PositionGetTicket(i);
            ulong Position_Magic_Number = PositionGetInteger(POSITION_MAGIC);
            if(Position_Magic_Number == magic_num)
            {
               total+=1;
            }
         }
      }
      return total;
   }
   
   /**
     * @brief Get lastest position volume.
     * 
     * @param magic_num value of Magic Number. 
     * @return Return volume lastest position.  
     */
     
   double LastVolumeByMagic(ulong magic_num)
   {
      double last_volume=0;
      
      if(PositionsTotal()>0 && PositionSelect(_Symbol)){
         for(int i=0; i<PositionsTotal();i++){
            ulong position_ticket=PositionGetTicket(i);
            ulong Position_Magic_Number = PositionGetInteger(POSITION_MAGIC);
            if(Position_Magic_Number == magic_num)
            {
               last_volume=PositionGetDouble(POSITION_VOLUME);
            }
         }
      }
      return last_volume;
   }
   
   /**
     * @brief Get total profit.
     * 
     * @param magic_num value of Magic Number. 
     * @return Return sum profit all position.  
     */
     
   double SumProfit(ulong magic_num)
   {
      double sum=0;
      if(PositionSelect(_Symbol))
      {
         for(int i=0; i<PositionsTotal(); i++)
         {
            ulong position_ticket=PositionGetTicket(i);
            ulong Position_Magic_Number = PositionGetInteger(POSITION_MAGIC);
            if(Position_Magic_Number == magic_num)
            {
               string position_symbol=PositionGetString(POSITION_SYMBOL);
               double profit=PositionGetDouble(POSITION_PROFIT);
               sum+=profit;
            }
         }
      }
      return sum;
   }
   
   /**
     * @brief get price open of last position.
     * 
     * @param magic_num value of Magic Number.  
     * @return Return price of last position. 
     */
   double LastOpenPrice(ulong magic_number)
   {
      double price_open=0;
      if(PositionsTotal()>0)
      {
         for(int i=0;i<PositionsTotal();i++)
         {
            ulong position_ticket=PositionGetTicket(i);
            ENUM_POSITION_TYPE position_type=(ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
            ulong Position_Magic_Number = PositionGetInteger(POSITION_MAGIC);
            if(Position_Magic_Number==magic_number)
            {
               price_open=PositionGetDouble(POSITION_PRICE_OPEN);
            } 
         }
      }
      return price_open;
   }   
   
   /**
     * @brief get price open of first position.
     * 
     * @param magic_num value of Magic Number.  
     * @return Return price of last position. 
     */
   double FirstOpenPrice(ulong magic_number)
   {
      double price_open=0;
      if(PositionsTotal()>0)
      {
         for(int i=PositionsTotal()-1;i>=0;i--)
         {
            ulong position_ticket=PositionGetTicket(i);
            ENUM_POSITION_TYPE position_type=(ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
            ulong Position_Magic_Number = PositionGetInteger(POSITION_MAGIC);
            if(Position_Magic_Number==magic_number)
            {
               price_open=PositionGetDouble(POSITION_PRICE_OPEN);
            } 
         }
      }
      return price_open;
   }

   /**
     * @brief get total position BUY.
     * 
     * @param magic_num value of Magic Number.  
     * @return Return total position with order BUY. 
     */
   int TotalBuy(ulong magic_number){
      int total=0;
      if(PositionsTotal()>0)
      {
         for(int i=PositionsTotal()-1;i>=0;i--)
         {
            ulong position_ticket=PositionGetTicket(i);
            ENUM_POSITION_TYPE position_type=(ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
            ulong Position_Magic_Number = PositionGetInteger(POSITION_MAGIC);
            if(Position_Magic_Number==magic_number && position_type==POSITION_TYPE_BUY)
            {
               total+=1;
            } 
         }
      }
      return total;
   }
   
   /**
     * @brief get total position SELL.
     * 
     * @param magic_num value of Magic Number.  
     * @return Return total position with order SELL. 
     */
   int TotalSell(ulong magic_number){
      int total=0;
      if(PositionsTotal()>0)
      {
         for(int i=PositionsTotal()-1;i>=0;i--)
         {
            ulong position_ticket=PositionGetTicket(i);
            ENUM_POSITION_TYPE position_type=(ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
            ulong Position_Magic_Number = PositionGetInteger(POSITION_MAGIC);
            if(Position_Magic_Number==magic_number && position_type==POSITION_TYPE_SELL)
            {
               total+=1;
            } 
         }
      }
      return total;
   }
   
   
   /**
     * @brief get min price of position.
     * 
     * @param type value is BUY or SELL. 
     * @param magic_num value of Magic Number.  
     * @param last_open price of last position order to compare with other position. 
     * @return Return max price in list position open. 
     */
   double MaxPriceOpen(ENUM_POSITION_TYPE type, ulong magic_number, double last_open)
   {
      double price=last_open;
      double price_open=0;
      if(PositionsTotal()>0)
      {
         for(int i=PositionsTotal()-1;i>=0; i--){
            ulong position_ticket=PositionGetTicket(i);
            ENUM_POSITION_TYPE position_type=(ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
            ulong Position_Magic_Number = PositionGetInteger(POSITION_MAGIC);
            if(Position_Magic_Number == magic_number && type==position_type)
            {
               price_open=PositionGetDouble(POSITION_PRICE_OPEN);
               if(price<price_open)
               {
                  price=price_open;
               }
            }
         }
      }
      return price;
   }
   
   /**
     * @brief get min price of position.
     * 
     * @param type value is BUY or SELL. 
     * @param magic_num value of Magic Number.  
     * @param last_open price of last position order to compare with other position. 
     * @return Return min price in list position open. 
     */
   double MinPriceOpen(ENUM_POSITION_TYPE type, ulong magic_number, double last_open)
   {
      double price=last_open;
      double price_open=0;
      if(PositionsTotal()>0)
      {
         for(int i=PositionsTotal()-1;i>=0; i--){
            ulong position_ticket=PositionGetTicket(i);
            ENUM_POSITION_TYPE position_type=(ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);
            ulong Position_Magic_Number = PositionGetInteger(POSITION_MAGIC);
            if(Position_Magic_Number == magic_number && type==position_type)
            {
               price_open=PositionGetDouble(POSITION_PRICE_OPEN);
               if(price>price_open)
               {
                  price=price_open;
               }
            }
         }
      }
      return price;
   }

   
   /**
     * @brief Close all position with magic number.
     * 
     * @param magic_num value of Magic Number.   
     */
     
   void CloseAllPositions(ulong magic_num)
   {
      MqlTradeRequest request;
      MqlTradeResult  result;
      int total=PositionsTotal(); // number of open positions   
      if(PositionSelect(_Symbol))
      {
         for(int i=total-1; i>=0; i--)
         {
            //--- parameters of the order
            ulong  position_ticket=PositionGetTicket(i);  // ticket of the position
            ulong Position_Magic_Number = PositionGetInteger(POSITION_MAGIC);
            if(Position_Magic_Number == magic_num)
            {
                                        
               double position_profit =PositionGetDouble(POSITION_PROFIT);
               
               string position_symbol=PositionGetString(POSITION_SYMBOL);                        // symbol 
               int    digits=(int)SymbolInfoInteger(position_symbol,SYMBOL_DIGITS);              // number of decimal places
               ulong  magic=PositionGetInteger(POSITION_MAGIC);                                  // MagicNumber of the position
               double volume=PositionGetDouble(POSITION_VOLUME);                                 // volume of the position
               ENUM_POSITION_TYPE type=(ENUM_POSITION_TYPE)PositionGetInteger(POSITION_TYPE);    // type of the position
               //--- output information about the position
               PrintFormat("#%I64u %s  %s  %.2f  %s [%I64d]",
                           position_ticket,
                           position_symbol,
                           EnumToString(type),
                           volume,
                           DoubleToString(PositionGetDouble(POSITION_PRICE_OPEN),digits),
                           magic);
               //--- zeroing the request and result values
               ZeroMemory(request);
               ZeroMemory(result);
               //--- setting the operation parameters
               request.action   = TRADE_ACTION_DEAL;        // type of trade operation
               request.position = position_ticket;          // ticket of the position
               request.symbol   = position_symbol;          // symbol 
               request.volume   = volume;                   // volume of the position
               request.deviation= 5;                        // allowed deviation from the price
               request.magic    = magic_num;             // MagicNumber of the position
               //--- set the price and order type depending on the position type
               if(type == POSITION_TYPE_BUY)
                 {
                  request.price=SymbolInfoDouble(position_symbol,SYMBOL_BID);
                  request.type =ORDER_TYPE_SELL;
                 }
               else
                 {
                  request.price=SymbolInfoDouble(position_symbol,SYMBOL_ASK);
                  request.type =ORDER_TYPE_BUY;
                 }
               //--- output information about the closure
               PrintFormat("Close #%I64d %s %s",position_ticket,position_symbol,EnumToString(type));
               //--- send the request
               if(!OrderSendAsync(request,result))
                  PrintFormat("OrderSend error %d",GetLastError());  // if unable to send the request, output the error code
               //--- information about the operation   
               PrintFormat("retcode=%u  deal=%I64u  order=%I64u",result.retcode,result.deal,result.order);
               //---
            }
         }
      }
   } 
}