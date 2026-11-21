#include <Trade/Trade.mqh>
#include <Arrays/ArrayLong.mqh>
#include "Symbol.mqh"
namespace FxceTrade
{
    /**
     * @brief Open a Market Buy order.
     * 
     * @param volume Requested order volume in lots. 
     * @param symbol Symbol of the order. In case of NULL means current symbol.
     * @param sl Stop Loss price in case of the unfavorable price movement.
     * @param tp Take Profit price in the case of the favorable price movement.
     * @param cmt Order comment.
     * @param magic Expert Advisor ID. It allows organizing analytical processing of trade orders. 
     *              Each Expert Advisor can set its own unique ID when sending a trade request.
     * @param async Used for conducting asynchronous trade operations without waiting for 
     *              the trade server's response to a sent request.
     * @return Return true in case successful, otherwise false.  
     */
    bool Buy(const double volume, const string symbol = NULL, const double sl = 0, const double tp = 0,
             const string cmt = "", const long magic = 0, const bool async = false)
    {
        CTrade trade;
        trade.SetAsyncMode(async);
        trade.SetExpertMagicNumber(magic);
        if (!trade.Buy(volume, symbol, 0, sl, tp, cmt))
        {
            Print(trade.ResultComment());
            return false;
        }

        return true;
    }
    /**
     * @brief Open a Buy Limit pending order.
     * 
     * @param volume Requested order volume in lots. 
     * @param price Price, reaching which the order must be executed.
     * @param symbol Symbol of the order. 
     *               It is not necessary for order modification and position close operations.
     * @param sl Stop Loss price in case of the unfavorable price movement.
     * @param tp Take Profit price in the case of the favorable price movement.
     * @param typeTime Order expiration type. Can be one of the enumeration ENUM_ORDER_TYPE_TIME values.
     * @param expiration Order expiration time (for orders of ORDER_TIME_SPECIFIED type).
     * @param cmt Order comment.
     * @param magic Expert Advisor ID. It allows organizing analytical processing of trade orders. 
     *              Each Expert Advisor can set its own unique ID when sending a trade request.
     * @param async Used for conducting asynchronous trade operations without waiting for 
     *              the trade server's response to a sent request.
     * @return Return true in case successful, otherwise false. 
     */
    bool BuyLimit(const double volume, const double price, const string symbol = NULL,
                  const double sl = 0, const double tp = 0, const ENUM_ORDER_TYPE_TIME typeTime = ORDER_TIME_GTC,
                  const datetime expiration = 0, const string cmt = "", const long magic = 0, const bool async = false)
    {
        CTrade trade;
        trade.SetAsyncMode(async);
        trade.SetExpertMagicNumber(magic);
        if (!trade.BuyLimit(volume, price, symbol, sl, tp, typeTime, expiration, cmt))
        {
            Print(trade.ResultComment());
            return false;
        }

        return true;
    }
    /**
     * @brief Open a Buy Stop pending order.
     * 
     * @param volume Requested order volume in lots. 
     * @param price Price, reaching which the order must be executed.
     * @param symbol Symbol of the order. It is not necessary for order modification and position close operations.
     * @param sl Stop Loss price in case of the unfavorable price movement.
     * @param tp Take Profit price in the case of the favorable price movement.
     * @param typeTime Order expiration type. Can be one of the enumeration ENUM_ORDER_TYPE_TIME values.
     * @param expiration Order expiration time (for orders of ORDER_TIME_SPECIFIED type).
     * @param cmt Order comment.
     * @param magic Expert Advisor ID. It allows organizing analytical processing of trade orders. 
     *              Each Expert Advisor can set its own unique ID when sending a trade request.
     * @param async Used for conducting asynchronous trade operations without waiting for 
     *              the trade server's response to a sent request.
     * @return Return true in case successful, otherwise false. 
     */
    bool BuyStop(const double volume, const double price, const string symbol = NULL,
                 const double sl = 0, const double tp = 0, const ENUM_ORDER_TYPE_TIME typeTime = ORDER_TIME_GTC,
                 const datetime expiration = 0, const string cmt = "", const long magic = 0, const bool async = false)
    {
        CTrade trade;
        trade.SetAsyncMode(async);
        trade.SetExpertMagicNumber(magic);
        if (!trade.BuyStop(volume, price, symbol, sl, tp, typeTime, expiration, cmt))
        {
            Print(trade.ResultComment());
            return false;
        }

        return true;
    }
    /**
     * @brief Open a Market Sell order.
     * 
     * @param volume Requested order volume in lots. 
     * @param symbol Symbol of the order. In case of NULL means current symbol.
     * @param sl Stop Loss price in case of the unfavorable price movement.
     * @param tp Take Profit price in the case of the favorable price movement.
     * @param cmt Order comment.
     * @param magic Expert Advisor ID. It allows organizing analytical processing of trade orders. 
     *              Each Expert Advisor can set its own unique ID when sending a trade request.
     * @param async Used for conducting asynchronous trade operations without waiting for 
     *              the trade server's response to a sent request.
     * @return Return true in case successful, otherwise false.  
     */
    bool Sell(const double volume, const string symbol = NULL, const double sl = 0, const double tp = 0,
              const string cmt = "", const long magic = 0, const bool async = false)
    {
        CTrade trade;
        trade.SetAsyncMode(async);
        trade.SetExpertMagicNumber(magic);
        if (!trade.Sell(volume, symbol, 0, sl, tp, cmt))
        {
            Print(trade.ResultComment());
            return false;
        }

        return true;
    }
    /**
     * @brief Open a Sell Limit pending order.
     * 
     * @param volume Requested order volume in lots. 
     * @param price Price, reaching which the order must be executed.
     * @param symbol Symbol of the order. It is not necessary for order modification and position close operations.
     * @param sl Stop Loss price in case of the unfavorable price movement.
     * @param tp Take Profit price in the case of the favorable price movement.
     * @param typeTime Order expiration type. Can be one of the enumeration ENUM_ORDER_TYPE_TIME values.
     * @param expiration Order expiration time (for orders of ORDER_TIME_SPECIFIED type).
     * @param cmt Order comment.
     * @param magic Expert Advisor ID. It allows organizing analytical processing of trade orders. 
     *              Each Expert Advisor can set its own unique ID when sending a trade request.
     * @param async sed for conducting asynchronous trade operations without waiting for 
     *              the trade server's response to a sent request.
     * @return Return true in case successful, otherwise false. 
     */
    bool SellLimit(const double volume, const double price, const string symbol = NULL,
                   const double sl = 0, const double tp = 0, const ENUM_ORDER_TYPE_TIME typeTime = ORDER_TIME_GTC,
                   const datetime expiration = 0, const string cmt = "", const long magic = 0, const bool async = false)
    {
        CTrade trade;
        trade.SetAsyncMode(async);
        trade.SetExpertMagicNumber(magic);
        if (!trade.SellLimit(volume, price, symbol, sl, tp, typeTime, expiration, cmt))
        {
            Print(trade.ResultComment());
            return false;
        }

        return true;
    }
    /**
     * @brief Open a Sell Stop pending order.
     * 
     * @param volume Requested order volume in lots. 
     * @param price Price, reaching which the order must be executed.
     * @param symbol Symbol of the order. It is not necessary for order modification and position close operations.
     * @param sl Stop Loss price in case of the unfavorable price movement.
     * @param tp Take Profit price in the case of the favorable price movement.
     * @param typeTime Order expiration type. Can be one of the enumeration ENUM_ORDER_TYPE_TIME values.
     * @param expiration Order expiration time (for orders of ORDER_TIME_SPECIFIED type).
     * @param cmt Order comment.
     * @param magic Expert Advisor ID. It allows organizing analytical processing of trade orders. 
     *              Each Expert Advisor can set its own unique ID when sending a trade request.
     * @param async Used for conducting asynchronous trade operations without waiting for 
     *              the trade server's response to a sent request.
     * @return Return true in case successful, otherwise false. 
     */
    bool SellStop(const double volume, const double price, const string symbol = NULL,
                  const double sl = 0, const double tp = 0, const ENUM_ORDER_TYPE_TIME typeTime = ORDER_TIME_GTC,
                  const datetime expiration = 0, const string cmt = "", const long magic = 0, const bool async = false)
    {
        CTrade trade;
        trade.SetAsyncMode(async);
        trade.SetExpertMagicNumber(magic);
        if (!trade.SellStop(volume, price, symbol, sl, tp, typeTime, expiration, cmt))
        {
            Print(trade.ResultComment());
            return false;
        }

        return true;
    }
    /**
     * @brief Modify Stop Loss and Take Profit values of an opened position.
     * 
     * @param ticket Ticket of a position will be modified.
     * @param sl Stop Loss price in case of the unfavorable price movement.
     * @param tp Take Profit price in the case of the favorable price movement.
     * @return Return true in case successful, otherwise false.  
     */
    bool ModifyPosition(const ulong ticket, const double sl, const double tp, const bool async = false)
    {
        CTrade trade;
        trade.SetAsyncMode(async);
        if (!trade.PositionModify(ticket, sl, tp))
        {
            Print(trade.ResultComment());
            return false;
        }
        return true;
    }
    /**
     * @brief Modify the parameters of the order placed previously
     * 
     * @param ticket Ticket of a pending order will be modified.
     * @param price Price, reaching which the order must be executed.
     * @param sl Stop Loss price in case of the unfavorable price movement.
     * @param tp Take Profit price in the case of the favorable price movement.
     * @param typeTime Order expiration type. Can be one of the enumeration ENUM_ORDER_TYPE_TIME values.
     * @param expiration Order expiration time (for orders of ORDER_TIME_SPECIFIED type).
     * @return Return true in case successful, otherwise false.   
     */
    bool ModifyOrder(const ulong ticket, const double price, const double sl, const double tp,
                     const ENUM_ORDER_TYPE_TIME typeTime = ORDER_TIME_GTC, const datetime expiration = 0, const bool async = false)
    {
        CTrade trade;
        trade.SetAsyncMode(async);
        if (!trade.OrderModify(ticket, price, sl, tp, typeTime, expiration))
        {
            Print(trade.ResultComment());
            return false;
        }
        return true;
    }
    /**
     * @brief Close an opening position.
     * 
     * @param ticket Ticket of a position will be closed.
     * @param percentage Percentag of volume is closed between 0 and 1.
     * @param deviation The maximal price deviation, specified in points.
     * @param async Used for conducting asynchronous trade operations without waiting for 
     *          the trade server's response to a sent request.
     * @return Return true in case successful, otherwise false.  
     */
    bool ClosePostion(const ulong ticket, const double percentage = 1, const ulong deviation = LONG_MAX, const bool async = false)
    {
        CTrade trade;
        trade.SetAsyncMode(async);
        if (MathAbs(percentage) >= 1)
        {
            if (!trade.PositionClose(ticket, deviation))
            {
                Print(trade.ResultComment());
                return false;
            }
        }
        else
        {
            CPositionInfo info;
            if (!info.SelectByTicket(ticket))
            {
                Print("Position select by ticket fail: ", GetLastError());
                return false;
            }

            string symbol = info.Symbol();
            double crrVolume = info.Volume();
            double closedVolume = crrVolume * MathAbs(percentage);
            closedVolume = FxceSymbol::NormalizeVolume(closedVolume, symbol);
            if (!trade.PositionClosePartial(ticket, closedVolume, deviation))
            {
                Print(trade.ResultComment());
                return false;
            }
        }

        return true;
    }
    /**
     * @brief Close all opening positions.
     * 
     * @param percentage Percentag of volume is closed between 0 and 1.
     * @param deviation The maximal price deviation, specified in points.
     * @param async Used for conducting asynchronous trade operations without waiting for 
     *              the trade server's response to a sent request.
     * @return The number of closed orders.   
     */
    int ClosePositions(const double percentage = 1, const ulong deviation = LONG_MAX, const bool async = false)
    {
        uint count = 0;

        CPositionInfo info;
        for (int i = PositionsTotal() - 1; i >= 0; i--)
        {
            if (!info.SelectByIndex(i))
            {
                continue;
            }

            if (ClosePostion(info.Ticket(), percentage, deviation, async))
            {
                count++;
            }
        }

        return count;
    }
    /**
     * @brief Close the opening positions by tickets.
     * 
     * @param tickets Array of tickets.
     * @param percentage Percentag of volume is closed between 0 and 1.
     * @param deviation The maximal price deviation, specified in points.
     * @param async Used for conducting asynchronous trade operations without waiting for 
     *              the trade server's response to a sent request.
     * @return The number of closed orders.
     */
    int ClosePositions(const ulong &tickets[], const double percentage = 1, const ulong deviation = LONG_MAX, const bool async = false)
    {
        uint count = 0;

        for (int i = ArraySize(tickets) - 1; i >= 0; i--)
        {
            ulong ticket = tickets[i];
            if (ClosePostion(ticket, percentage, deviation, async))
            {
                count++;
            }
        }

        return count;
    }
    /**
     * @brief Close the opening positions by magic number.
     * 
     * @param magic Input magic number.
     * @param percentage Percentag of volume is closed between 0 and 1.
     * @param deviation The maximal price deviation, specified in points.
     * @param async Used for conducting asynchronous trade operations without waiting for 
     *              the trade server's response to a sent request.
     * @return The number of closed orders. 
     */
    int ClosePositions(const ulong magic, const double percentage = 1, const ulong deviation = LONG_MAX, const bool async = false)
    {
        uint count = 0;

        CPositionInfo info;
        for (int i = PositionsTotal() - 1; i >= 0; i--)
        {
            if (!info.SelectByIndex(i))
            {
                continue;
            }

            if (info.Magic() == magic)
            {
                if (ClosePostion(info.Ticket(), percentage, deviation, async))
                {
                    count++;
                }
            }
        }

        return count;
    }
    /**
     * @brief Close the opening positions by symbol.
     * 
     * @param symbol Input symbol.
     * @param percentage Percentag of volume is closed between 0 and 1.
     * @param deviation The maximal price deviation, specified in points.
     * @param async Used for conducting asynchronous trade operations without waiting for 
     *              the trade server's response to a sent request.
     * @return The number of closed orders. 
     */
    int ClosePositions(const string symbol, const double percentage = 1, const ulong deviation = LONG_MAX, const bool async = false)
    {
        uint count = 0;

        CPositionInfo info;
        for (int i = PositionsTotal() - 1; i >= 0; i--)
        {
            if (!info.SelectByIndex(i))
            {
                continue;
            }

            if (info.Symbol() == symbol)
            {
                if (ClosePostion(info.Ticket(), percentage, deviation, async))
                {
                    count++;
                }
            }
        }

        return count;
    }
    /**
     * @brief Close the opening positions by type.
     * 
     * @param type Type of position. 
     *             The value can be one of the values of the ENUM_POSITION_TYPE enumeration.
     * @param percentage Percentag of volume is closed between 0 and 1.
     * @param deviation The maximal price deviation, specified in points.
     * @param async Used for conducting asynchronous trade operations without waiting for 
     *              the trade server's response to a sent request.
     * @return The number of closed orders.   
     */
    int ClosePositions(ENUM_POSITION_TYPE type, const double percentage = 1, const ulong deviation = LONG_MAX, const bool async = false)
    {
        uint count = 0;

        CPositionInfo info;
        for (int i = PositionsTotal() - 1; i >= 0; i--)
        {
            if (!info.SelectByIndex(i))
            {
                continue;
            }

            if (info.PositionType() == type)
            {
                if (ClosePostion(info.Ticket(), percentage, deviation, async))
                {
                    count++;
                }
            }
        }

        return count;
    }
    /**
     * @brief Close the opening positions by symbol and type.
     * 
     * @param symbol Input symbol.
     * @param type Type of position. 
     *             The value can be one of the values of the ENUM_POSITION_TYPE enumeration.
     * @param percentage Percentag of volume is closed between 0 and 1.
     * @param deviation The maximal price deviation, specified in points.
     * @param async Used for conducting asynchronous trade operations without waiting for 
     *              the trade server's response to a sent request.
     * @return The number of closed orders.  
     */
    int ClosePositions(const string symbol, ENUM_POSITION_TYPE type, const double percentage = 1, const ulong deviation = LONG_MAX, const bool async = false)
    {
        uint count = 0;

        CPositionInfo info;
        for (int i = PositionsTotal() - 1; i >= 0; i--)
        {
            if (!info.SelectByIndex(i))
            {
                continue;
            }

            if (info.Symbol() == symbol && info.PositionType() == type)
            {
                if (ClosePostion(info.Ticket(), percentage, deviation, async))
                {
                    count++;
                }
            }
        }

        return count;
    }
    /**
     * @brief Delete a pending order.
     * 
     * @param ticket Ticket of a pending order will be Deleted.
     * @param async Used for conducting asynchronous trade operations without waiting for 
     *              the trade server's response to a sent request.
     * @return Return true in case successful, otherwise false. 
     */
    bool DeleteOrder(const ulong ticket, const bool async = false)
    {
        CTrade trade;
        trade.SetAsyncMode(async);

        if (!trade.OrderDelete(ticket))
        {
            Print(trade.ResultComment());
            return false;
        }

        return true;
    }
    /**
     * @brief Delete all the pending orders.
     * 
     * @param async Used for conducting asynchronous trade operations without waiting for 
     *              the trade server's response to a sent request.
     * @return The number of closed orders. 
     */
    int DeleteOrders(const bool async = false)
    {
        uint count = 0;

        COrderInfo info;
        for (int i = OrdersTotal() - 1; i >= 0; i--)
        {
            if (info.SelectByIndex(i))
            {
                if (DeleteOrder(info.Ticket(), async))
                {
                    count++;
                }
            }
        }

        return count;
    }
    /**
     * @brief Delete the pending orders from list.
     * 
     * @param tickets Array of tickets.
     * @param async Used for conducting asynchronous trade operations without waiting for 
     *             the trade server's response to a sent request.
     * @return The number of closed orders.    
     */
    int DeleteOrders(const ulong &tickets[], bool async = false)
    {
        uint count = 0;
        for (int i = ArraySize(tickets) - 1; i >= 0; i--)
        {
            ulong ticket = tickets[i];
            if (DeleteOrder(ticket, async))
            {
                count++;
            }
        }

        return count;
    }
    /**
     * @brief Delete the pending orders by magic number.
     * 
     * @param magic Input magic number.
     * @param async Used for conducting asynchronous trade operations without waiting for 
     *              the trade server's response to a sent request.
     * @return The number of closed orders. 
     */
    int DeleteOrders(const ulong magic, const bool async = false)
    {
        uint count = 0;

        COrderInfo info;
        for (int i = OrdersTotal() - 1; i >= 0; i--)
        {
            if (!info.SelectByIndex(i))
            {
                continue;
            }

            if (info.Magic() == magic)
            {
                if (DeleteOrder(info.Ticket(), async))
                {
                    count++;
                }
            }
        }

        return count;
    }
    /**
     * @brief Delete the pending orders by type.
     * 
     * @param type Type of order. 
     *             The value can be one of the values of the ENUM_ORDER_TYPE enumeration.
     * @param async Used for conducting asynchronous trade operations without waiting for 
     *              the trade server's response to a sent request.
     * @return The number of closed orders.   
     */
    int DeleteOrders(const ENUM_ORDER_TYPE type, const bool async = false)
    {
        uint count = 0;

        COrderInfo info;
        for (int i = OrdersTotal() - 1; i >= 0; i--)
        {
            if (!info.SelectByIndex(i))
            {
                continue;
            }

            if (info.OrderType() == type)
            {
                if (DeleteOrder(info.Ticket(), async))
                {
                    count++;
                }
            }
        }

        return count;
    }
    /**
     * @brief Delete the pending orders by symbol.
     * 
     * @param symbol Input symbol.
     * @param async Used for conducting asynchronous trade operations without waiting for 
     *              the trade server's response to a sent request.
     * @return The number of closed orders. 
     */
    int DeleteOrders(const string symbol, const bool async = false)
    {
        uint count = 0;

        COrderInfo info;
        for (int i = OrdersTotal() - 1; i >= 0; i--)
        {
            if (!info.SelectByIndex(i))
            {
                continue;
            }

            if (info.Symbol() == symbol)
            {
                if (DeleteOrder(info.Ticket(), async))
                {
                    count++;
                }
            }
        }

        return count;
    }
    /**
     * @brief Delete the pending orders by symbol and type.
     * 
     * @param symbol Input symbol.
     * @param type Type of position. 
     *             The value can be one of the values of the ENUM_ORDER_TYPE enumeration.
     * @param async Used for conducting asynchronous trade operations without waiting for 
     *              the trade server's response to a sent request.
     * @return The number of closed orders.  
     */
    int DeleteOrders(const string symbol, ENUM_ORDER_TYPE type, const bool async = false)
    {
        uint count = 0;

        COrderInfo info;
        for (int i = OrdersTotal() - 1; i >= 0; i--)
        {
            if (!info.SelectByIndex(i))
            {
                continue;
            }

            if (info.Symbol() == symbol && info.OrderType() == type)
            {
                if (DeleteOrder(info.Ticket(), async))
                {
                    count++;
                }
            }
        }

        return count;
    }
    /**
     * @brief Count history profit by position.
     * 
     * @param position Position Id.
     * @param includeCommission Include commission.
     * @param includeSwap Include swap.
     * @return Value of double type.   
     */
    double HistoryProfit(const ulong position, const bool includeCommission = true, const bool includeSwap = true)
    {
        double profit = 0;
        if (HistorySelectByPosition(position))
        {
            CDealInfo deal;
            for (int i = 0; i < HistoryDealsTotal(); i++)
            {
                if (!deal.SelectByIndex(i))
                {
                    continue;
                }

                if (includeCommission)
                {
                    profit += deal.Commission();
                }

                if (includeSwap)
                {
                    profit += deal.Swap();
                }

                profit += deal.Profit();
            }
        }

        return profit;
    }
    /**
     * @brief Count history profit of all deals in specified period.
     * 
     * @param from From.
     * @param to To.
     * @param includeCommission Include commission.
     * @param includeSwap Include swap.
     * @return Value of double type.  
     */
    double HistoryProfit(const datetime from, const datetime to, const bool includeCommission = true, const bool includeSwap = true)
    {
        double profit = 0;
        CArrayLong positions;

        if (HistorySelect(from, to))
        {
            CDealInfo deal;
            for (int i = 0; i < HistoryDealsTotal(); i++)
            {
                if (!deal.SelectByIndex(i))
                {
                    continue;
                }

                if (deal.Entry() == DEAL_ENTRY_IN)
                {
                    positions.Add(deal.PositionId());
                }
            }
        }

        for (int i = 0; i < positions.Total(); i++)
        {
            profit += HistoryProfit(positions.At(i), includeCommission, includeSwap);
        }

        return profit;
    }
    /**
     * @brief Count history profit of all deals in specified period by magic number.
     * 
     * @param from From.
     * @param to To.
     * @param magic Magic number.
     * @param includeCommission Include commission.
     * @param includeSwap Include swap.
     * @return Value of double type.  
     */
    double HistoryProfit(const datetime from, const datetime to, const ulong magic, const bool includeCommission = true, const bool includeSwap = true)
    {
        double profit = 0;
        CArrayLong positions;

        if (HistorySelect(from, to))
        {
            CDealInfo deal;
            for (int i = 0; i < HistoryDealsTotal(); i++)
            {
                if (!deal.SelectByIndex(i))
                {
                    continue;
                }

                if (deal.Entry() == DEAL_ENTRY_IN && deal.Magic() == magic)
                {
                    positions.Add(deal.PositionId());
                }
            }
        }

        for (int i = 0; i < positions.Total(); i++)
        {
            profit += HistoryProfit(positions.At(i), includeCommission, includeSwap);
        }

        return profit;
    }
    /**
     * @brief Count profit of opening position.
     * 
     * @param ticket Position ticket.
     * @param includeCommission Include commission.
     * @param includeSwap Include swap.
     * @return Value of double type.   
     */
    double ProfitPosition(const ulong ticket, const bool includeCommission = true, const bool includeSwap = true)
    {
        double profit = 0;
        CPositionInfo info;
        if (info.SelectByTicket(ticket))
        {
            if (includeCommission)
            {
                profit += info.Commission();
            }
            if (includeSwap)
            {
                profit += info.Swap();
            }
            profit += info.Profit();
        }

        return profit;
    }
    /**
     * @brief Count profit of all opening positions.
     * 
     * @param magic Magic number.
     * @param includeCommission Include commission.
     * @param includeSwap Include swap.
     * @return Value of double type.   
     */
    double ProfitPositions(const bool includeCommission = true, const bool includeSwap = true)
    {
        double profit = 0;

        CPositionInfo info;
        for (int i = 0; i < PositionsTotal(); i++)
        {
            if (!info.SelectByIndex(i))
            {
                continue;
            }

            profit += ProfitPosition(info.Ticket(), includeCommission, includeSwap);
        }

        return profit;
    }
    /**
     * @brief Count profit of all opening positions by magic number.
     * 
     * @param magic Magic number.
     * @param includeCommission Include commission.
     * @param includeSwap Include swap.
     * @return Value of double type.   
     */
    double ProfitPositions(const ulong magic, const bool includeCommission = true, const bool includeSwap = true)
    {
        double profit = 0;

        CPositionInfo info;
        for (int i = 0; i < PositionsTotal(); i++)
        {
            if (!info.SelectByIndex(i))
            {
                continue;
            }

            if (info.Magic() != magic)
            {
                continue;
            }

            profit += ProfitPosition(info.Ticket(), includeCommission, includeSwap);
        }

        return profit;
    }
}