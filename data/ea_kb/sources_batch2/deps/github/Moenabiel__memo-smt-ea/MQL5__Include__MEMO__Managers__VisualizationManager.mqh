#ifndef MEMO_MANAGERS_VISUALIZATION_MANAGER_MQH
#define MEMO_MANAGERS_VISUALIZATION_MANAGER_MQH

#include <MEMO\Core\Settings.mqh>
#include <MEMO\Managers\StatisticsManager.mqh>

class CVisualizationManager
{
private:
   MEMO_Settings m_settings;
   string m_prefix;

   void SetLine(const string name, const double price, const color clr, const ENUM_LINE_STYLE style) const
   {
      const string object_name = m_prefix + name;
      if(ObjectFind(0, object_name) < 0)
         ObjectCreate(0, object_name, OBJ_HLINE, 0, 0, price);

      ObjectSetDouble(0, object_name, OBJPROP_PRICE, price);
      ObjectSetInteger(0, object_name, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, object_name, OBJPROP_STYLE, style);
      ObjectSetInteger(0, object_name, OBJPROP_WIDTH, 1);
      ObjectSetInteger(0, object_name, OBJPROP_BACK, true);
   }

   void DrawRange(const MEMO_PriceRange &range, const string key, const color clr) const
   {
      if(!range.valid)
         return;
      SetLine(key + "_HIGH", range.high, clr, STYLE_DOT);
      SetLine(key + "_LOW", range.low, clr, STYLE_DOT);
   }

   void DrawRectangle(const string name,
                      const datetime left,
                      const datetime right,
                      const double lower,
                      const double upper,
                      const color clr) const
   {
      const string object_name = m_prefix + name;
      const datetime r = right > left ? right : TimeCurrent() + PeriodSeconds(PERIOD_H1);

      if(ObjectFind(0, object_name) < 0)
         ObjectCreate(0, object_name, OBJ_RECTANGLE, 0, left, lower, r, upper);

      ObjectSetInteger(0, object_name, OBJPROP_TIME, 0, left);
      ObjectSetDouble(0, object_name, OBJPROP_PRICE, 0, lower);
      ObjectSetInteger(0, object_name, OBJPROP_TIME, 1, r);
      ObjectSetDouble(0, object_name, OBJPROP_PRICE, 1, upper);
      ObjectSetInteger(0, object_name, OBJPROP_COLOR, clr);
      ObjectSetInteger(0, object_name, OBJPROP_FILL, true);
      ObjectSetInteger(0, object_name, OBJPROP_BACK, true);
   }

public:
   CVisualizationManager()
   {
      m_prefix = "MEMO_SMT_";
   }

   void Init(const MEMO_Settings &settings)
   {
      m_settings = settings;
   }

   void Clear()
   {
      for(int i = ObjectsTotal(0, -1, -1) - 1; i >= 0; i--)
      {
         const string name = ObjectName(0, i, -1, -1);
         if(StringFind(name, m_prefix) == 0)
            ObjectDelete(0, name);
      }
   }

   void DrawLiquidity(const MEMO_LiquidityMap &map) const
   {
      if(!m_settings.enable_visuals)
         return;

      DrawRange(map.previous_day, map.symbol + "_PD", m_settings.neutral_color);
      DrawRange(map.previous_week, map.symbol + "_PW", clrSlateGray);
      DrawRange(map.asia, map.symbol + "_ASIA", clrDarkSlateGray);
      DrawRange(map.london, map.symbol + "_LONDON", clrSteelBlue);
      DrawRange(map.newyork, map.symbol + "_NY", clrDarkOrange);
      DrawRange(map.ny_opening_range, map.symbol + "_NYOR", clrGoldenrod);
   }

   void DrawSetup(const MEMO_SetupContext &context) const
   {
      if(!m_settings.enable_visuals || !context.valid)
         return;

      const color setup_color = context.direction == MEMO_DIR_BUY ? m_settings.buy_color : m_settings.sell_color;
      if(context.fvg.valid)
         DrawRectangle(context.symbol + "_FVG", context.fvg.left_time, TimeCurrent() + PeriodSeconds(PERIOD_H4), context.fvg.lower, context.fvg.upper, setup_color);
      if(context.order_block.valid)
         DrawRectangle(context.symbol + "_OB", context.order_block.time, TimeCurrent() + PeriodSeconds(PERIOD_H4), context.order_block.lower, context.order_block.upper, setup_color);

      if(context.entry_price > 0.0)
         SetLine(context.symbol + "_ENTRY", context.entry_price, setup_color, STYLE_SOLID);
      if(context.stop_loss > 0.0)
         SetLine(context.symbol + "_SL", context.stop_loss, clrFireBrick, STYLE_SOLID);
      if(context.take_profit_1 > 0.0)
         SetLine(context.symbol + "_TP1", context.take_profit_1, clrSeaGreen, STYLE_DASH);
      if(context.take_profit_2 > 0.0)
         SetLine(context.symbol + "_TP2", context.take_profit_2, clrGreen, STYLE_SOLID);
   }

   void UpdatePanel(const MEMO_SetupContext &context, const string stats, const string status) const
   {
      if(!m_settings.enable_visuals)
         return;

      const string name = m_prefix + "PANEL";
      if(ObjectFind(0, name) < 0)
         ObjectCreate(0, name, OBJ_LABEL, 0, 0, 0);

      string text = "MEMO XAU/XAG SMT\n";
      text += "Status: " + status + "\n";
      text += "Symbol: " + (context.symbol == "" ? "-" : context.symbol) + " " + MEMO_DirectionText(context.direction) + "\n";
      text += "Score: " + IntegerToString(context.score.total) + "\n";
      text += "Regime: " + MEMO_RegimeText(context.regime.regime) + "\n";
      text += "Corr: " + DoubleToString(context.correlation, 3) + "\n";
      text += stats;

      ObjectSetString(0, name, OBJPROP_TEXT, text);
      ObjectSetInteger(0, name, OBJPROP_CORNER, m_settings.panel_corner);
      ObjectSetInteger(0, name, OBJPROP_XDISTANCE, 12);
      ObjectSetInteger(0, name, OBJPROP_YDISTANCE, 18);
      ObjectSetInteger(0, name, OBJPROP_COLOR, clrWhite);
      ObjectSetInteger(0, name, OBJPROP_FONTSIZE, 9);
      ObjectSetString(0, name, OBJPROP_FONT, "Consolas");
   }
};

#endif
