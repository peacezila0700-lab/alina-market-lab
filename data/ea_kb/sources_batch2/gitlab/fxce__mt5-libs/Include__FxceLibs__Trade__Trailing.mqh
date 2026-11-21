//+------------------------------------------------------------------+
//|                                                     Trailing.mqh |
//|                                        Copyright 2021, Fxce Ltd. |
//|                                             https://www.fxce.com |
//+------------------------------------------------------------------+
#property copyright "Copyright 2021, Fxce Ltd."
#property link      "https://www.fxce.com"

#include <FxceLibs\Trade\Trade.mqh>;

class FxceTrailing{
   private:
      string symbol;
      ulong ticket;
      double entry;
      double cur_sl;
      double cur_tp;
   public:
      FxceTrailing(string tsymbol, ulong ticket, double entry, double sl, double tp);
      bool TrailingPoint(int point);
      bool TrailingStep(int point_trailing, int point_step);
      bool MoveToBreakEvent(int point_move);
};

/**
  * @brief Constructor .
  * 
  * @param tsymbol Symbol trading.
  * @param tk Ticket of position.
  * @param open Entry position.
  * @param sl Stop loss of position.
  * @param tp Take profit of position.
  */
  
FxceTrailing::FxceTrailing(string tsymbol, ulong tk, double open,double sl,double tp)
{
   symbol=tsymbol;
   ticket=tk;
   entry=open;
   cur_sl=sl;
   cur_tp=tp;
}

/**
  * @brief trailing with point, always keep the distance SL and Price with the number of points .
  * 
  * @param point number point to trailing.
  * @return The result trailing. 
  */
     
bool FxceTrailing::TrailingPoint(int point)
{
   if(point>0)
   {
      double trail_stop=point*SymbolInfoDouble(symbol,SYMBOL_POINT);
      long pos_type = PositionGetInteger(POSITION_TYPE);
      double trail_stop_price;
      
      if(pos_type==POSITION_TYPE_BUY)
      {
         trail_stop_price=SymbolInfoDouble(symbol,SYMBOL_BID)-trail_stop;
         if(cur_sl<trail_stop_price)
         {
            if(!FxceTrade::ModifyPosition(ticket,trail_stop_price,cur_tp,true))
            {
               Print("Traling fail: "+(string)ticket);
               return false;
            }
            cur_sl=trail_stop_price;
         }
      }
      else if(pos_type==POSITION_TYPE_SELL)
      {
         trail_stop_price=SymbolInfoDouble(symbol,SYMBOL_ASK)+trail_stop;
         if(cur_sl>trail_stop_price)
         {
            if(!FxceTrade::ModifyPosition(ticket,trail_stop_price,cur_tp,true))
            {
                Print("Traling fail: "+(string)ticket);
               return false;
            }
            cur_sl=trail_stop_price;
         }
      }
   }
   return true;
}

/**
  * @brief trailing with step, price go to with step point will trailing .
  * 
  * @param point_trailing number point to trailing.
  * @param point_step number point step condition for trailing.
  * @return The result trailing. 
  */
  
bool FxceTrailing::TrailingStep(int point_trailing, int point_step)
{
   if(point_step>0)
   {
      double trail_stop=point_trailing*SymbolInfoDouble(symbol,SYMBOL_POINT);
      double trail_step=point_step*SymbolInfoDouble(symbol,SYMBOL_POINT);
      long pos_type = PositionGetInteger(POSITION_TYPE);
      double trail_stop_price;
      
      if(pos_type==POSITION_TYPE_BUY)
      {
         double next_step_price=cur_sl+trail_step;
         double Bid_price=SymbolInfoDouble(symbol,SYMBOL_BID);
         trail_stop_price=cur_sl+trail_stop;
         if(Bid_price>next_step_price)
         {
            if(!FxceTrade::ModifyPosition(ticket,trail_stop_price,cur_tp,true))
            {
                Print("Traling fail: "+(string)ticket);
                return false;
            }
         }  
      }
      else if(pos_type==POSITION_TYPE_SELL)
      {
         double next_step_price=cur_sl-trail_step;
         double Ask_price=SymbolInfoDouble(symbol,SYMBOL_ASK);
         trail_stop_price=cur_sl-trail_stop;
         if(Ask_price<next_step_price)
         {
            if(!FxceTrade::ModifyPosition(ticket,trail_stop_price,cur_tp,true))
            {
                Print("Traling fail: "+(string)ticket);
                 return false;
            }    
         }
      }
   }
   
   return true;
}

/**
  * @brief move SL to break event .
  * 
  * @param point_move number point step condition for move SL.
  * @return The result after move. 
  */
  
bool FxceTrailing::MoveToBreakEvent(int point_move)
{
   if(point_move>0 && cur_sl<entry)
   {
      double move_position=point_move*SymbolInfoDouble(symbol,SYMBOL_POINT);
      long pos_type = PositionGetInteger(POSITION_TYPE);
      double trail_stop_price;
      
      if(pos_type==POSITION_TYPE_BUY)
      {
         double check_move=entry+move_position;
         double Bid_price=SymbolInfoDouble(symbol,SYMBOL_BID);
         trail_stop_price=entry;
         
         if(Bid_price>check_move)
         {
            if(!FxceTrade::ModifyPosition(ticket,trail_stop_price,cur_tp,true))
            {
                Print("Move to breake event fail: "+(string)ticket);
                return false;
            }
         }  
      }
      else if(pos_type==POSITION_TYPE_SELL)
      {
         double check_move=entry-move_position;
         double Ask_price=SymbolInfoDouble(symbol,SYMBOL_ASK);
         trail_stop_price=entry;
         if(Ask_price<check_move)
         {
            if(!FxceTrade::ModifyPosition(ticket,trail_stop_price,cur_tp,true))
            {
                Print("Move to break event fail: "+(string)ticket);
                return false;
            }    
         }
      }
   }
   return true;
}
