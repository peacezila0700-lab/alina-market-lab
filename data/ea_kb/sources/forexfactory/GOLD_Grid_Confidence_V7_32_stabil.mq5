//+------------------------------------------------------------------+
//|                                  GOLD_Grid_Confidence_V7_32.mq5  |
//|                                  Copyright © 2026, AYDIN SARIHAN |
//|          XAUUSD Dinamik Lineer Grid & Hibrit TP Algoritması      |
//|                 https://www.mql5.com/en/users/aydinsarihan       |
//+------------------------------------------------------------------+
#property copyright "Copyright © 2026, AYDIN SARIHAN"
#property link      "https://www.mql5.com/en/users/aydinsarihan"
#property version   "7.32"
/// Değişiklik: V7.32 - Marti_Vir_v6_7 Sanal İşlem ve M5 Filtreleri eklendi.
#property strict
#property description "V7.32 - İdeal Hesap + Modüler Sanal Takip ve Giriş Filtreleri"

#include <Trade\Trade.mqh>
#include <Math\Stat\Math.mqh>

//--- Numaralandırmalar (Enums)
enum ENUM_TP_STRATEGY {
   TP_VIRTUAL_DOLLAR,    // 1) Sanal Sabit Dolar TP (V7.22 İdeal)
   TP_VIRTUAL_SK,        // 2) Sanal Sekanas TP (V7.22 Yedek)
   TP_PHYSICAL_AVERAGE,  // 3) Fiziksel Ortalama TP (SkScalp v2.2)
   TP_PHYSICAL_INDIV     // 4) Fiziksel Bireysel TP (SkScalp v2.2)
};

//==================================================================
// BÖLÜM 1: GİRİŞ PARAMETRELERİ
//==================================================================
input group "=== KİMLİK (IDENTITY) ===";
input int    InpAlisMagic              = 654321;          // Alış (BUY) Magic Numarası
input int    InpSatisMagic             = 654322;          // Satış (SELL) Magic Numarası

input group "=== SANAL İŞLEM (VIRTUAL TRADING) ===";
/// Değişiklik: Sanal işlem takibi parametreleri eklendi.
input bool   InpUseVirtualTrading      = false;           // Sanal İşlem Modu Açık/Kapalı
input double InpVirtualThreshold       = 0.04;            // Gerçek İşleme Geçiş Lot Eşiği
input double InpRealLotMultiplier      = 0.125;           // Gerçek Lot Çarpanı (Sanal Lot * X)

input group "=== GİRİŞ FİLTRELERİ (M5 TREND) ===";
/// Değişiklik: Marti M5 giriş filtreleri eklendi.
input bool   InpUseMartiEma            = false;           // M5 EMA (5/16) Kesişim Filtresi
input int    InpEmaFastPeriod          = 5;               // Hızlı EMA Periyodu
input int    InpEmaSlowPeriod          = 16;              // Yavaş EMA Periyodu
input bool   InpUseAdxFilter           = false;           // ADX Trend Filtresi (M5)
input int    InpAdxPeriod              = 14;              // ADX Periyodu
input double InpAdxMinLevel            = 25.0;            // Minimum ADX Seviyesi
input bool   InpUseVwapFilter          = false;           // Günlük VWAP Filtresi (M5)

input group "=== SİNYAL EŞİKLERİ (İlk Giriş İçin) ===";
input double InpNormalEsik             = 50.0;            // Normal Sinyal Eşiği (Confidence)
input double InpYumusatilmisEsik       = 20.0;            // Yumuşatılmış Eşik
input bool   InpGridEklemeSinyalIster  = false;           // Grid eklemeleri sinyal istesin mi?

input group "=== HACİM (LOT) DİZİLİMİ — Lineer ===";
input double InpBaslangicLot           = 0.01;            // Başlangıç Lot
input double InpLotArtisi              = 0.01;            // Kademe Başına Lot Artışı
input int    InpKademeBasinaTekrar     = 5;               // Basamak (Level) İçi Tekrar Sayısı
input double InpYondeMaxToplamLot      = 15.0;            // Yönde Toplam Lot Tavanı
input int    InpMaxGridKademe          = 20;              // Yönde Maksimum Grid Kademesi

input group "=== SEKANAS MESAFE KURALLARI ===";
input double InpL0IciMesafeSk          = 4.0;             // Basamak İçi Mesafe (Sk)
input double InpL0AtrCarpan            = 0.05;            // Basamak İçi ATR Çarpanı
input double InpAnaKademeMesafeSk      = 9.0;             // Basamak Arası Mesafe (Sk)
input double InpAnaKademeAtrCarpan     = 0.08;            // Basamak Arası ATR Çarpanı
input double InpKayipTarafSpacingCarpan= 1.3;             // Zarardaki Yön İçin Mesafe Genişletme Çarpanı

input group "=== ANA KÂR AL (TP) STRATEJİSİ ===";
input ENUM_TP_STRATEGY InpTPStrategy   = TP_VIRTUAL_DOLLAR; // Kullanılacak Kâr Al (TP) Yaklaşımı

input group "=== SANAL TP AYARLARI (Seçenek 1 & 2 İçin) ===";
input double InpSabitDolarTP           = 25.0;            // (1) Sepet sabit dolar hedefi ($)
input double InpMajorBonus             = 3.0;             // (1) Her major level için ek hedef ($)
input double InpMaxSabitTP             = 80.0;            // (1) Üst tavan ($)
input double InpBaseTPSk               = 50.0;            // (2) İlk İşlem Hedefi (Sekanas)
input double InpDropPerLotStepSk       = 1.0;             // (2) Her Lot Adımında Düşülecek Hedef
input double InpLotStepForDrop         = 0.01;            // (2) Hedef Düşürme Lot Adımı
input double InpMinTPSk                = 5.0;             // (2) Düşebilecek Min TP (Sekanas)

input group "=== FİZİKSEL TP VE İZLEYEN STOP (Seçenek 3 & 4 İçin - SkScalp) ===";
input double InpPhysicalTPSk           = 200.0;            // (3,4) Fiziksel Kâr Hedefi (Sekanas)
input bool   InpUseTrailing            = true;           // İzleyen Stop (Trailing Stop) Etkinleştir
input double InpProfitToStartTrail     = 10.0;            // İzlemeyi Başlatmak İçin Sepet Karı ($)
input double InpTrailStartSk           = 5.0;            // İzleme Başlangıcı (Sekanas)
input double InpTrailStepSk            = 2.0;             // İzleme Adımı (Sekanas)
input bool   InpTrailOnlyLast          = true;            // Sadece Son Emri mi İzle?
input bool   InpUseStopLoss            = true;           // Zarar Sınırını Etkinleştir?
input double InpFixedStopLossSk        = 250.0;           // Zarar Sınırı (Sekanas)

input group "=== GÜVENLİK (SAFETY) ===";
input double InpMaxDrawdownYuzde       = 50.0;            // Maksimum Drawdown (%)
input double InpMinEquity              = 50.0;            // Minimum Equity ($)
input int    InpSlippage               = 50;              // Slippage (point)
input double InpMaxSpreadDolar         = 0.5;             // Maksimum Spread ($)
input int    InpEmirGecikmeMs          = 500;             // Emir Gecikmesi (ms)

input group "=== PANEL AYARLARI (UI) ===";
input int    InpPanelX                 = 20;              // Panel X
input int    InpPanelY                 = 50;              // Panel Y

//==================================================================
// BÖLÜM 2: SABİTLER, GLOBAL DEĞİŞKENLER VE SANAL YAPI
//==================================================================
#define PANEL_W 380
#define PANEL_H 340 /// Değişiklik: Panel yüksekliği yeni öğeler için artırıldı
#define UI_PREFIX "GOLDV732_UI_"
#define MAX_VIRTUAL_POS 200 /// Değişiklik: Sanal pozisyon dizisi limiti

#define CLR_BG_MAIN      C'30,40,45'
#define CLR_BG_BOX       C'20,28,32'
#define CLR_BORDER       C'60,70,75'
#define CLR_TEXT_LBL     C'160,170,180'
#define CLR_TEXT_VAL     clrWhite
#define CLR_ACCENT       clrGold
#define CLR_ACTIVE       clrLime
#define CLR_PASSIVE      C'255,100,100'

CTrade   g_trade_buy;
CTrade   g_trade_sell;
datetime g_lastBarTime = 0;
ulong    g_lastOrderTimeMs = 0;

// İndikatör Handle'ları
int g_handle_ema20 = INVALID_HANDLE;
int g_handle_ema50 = INVALID_HANDLE;
int g_handle_rsi14 = INVALID_HANDLE;
int g_handle_atr5  = INVALID_HANDLE;

// Yeni İndikatör Handle'ları (M5)
int g_handle_m5_emaFast = INVALID_HANDLE;
int g_handle_m5_emaSlow = INVALID_HANDLE;
int g_handle_m5_adx     = INVALID_HANDLE;

int    g_total_baskets         = 0;
double g_last_confidence       = 0.0;
double g_active_buy_thr        = 0.0;
double g_active_sell_thr       = 0.0;
string g_last_prediction_str   = "NÖTR";
double g_account_peak_equity   = 0.0;
double g_dynamic_basetp        = 0.0;

enum ENUM_SIGNAL { SIGNAL_BUY, SIGNAL_SELL, SIGNAL_NONE };

/// Değişiklik: Sanal İşlem Veri Yapısı
struct VirtualPosition
{
   int      magic;
   int      type;       // 0: BUY, 1: SELL
   double   openPrice;
   double   volume;
   datetime openTime;
   bool     isActive;
   bool     isRealSpawned; // Eşik geçilip MT5'e emir iletildi mi?
};

VirtualPosition g_vPos[MAX_VIRTUAL_POS];
int g_vCount = 0;

// Filtre Durum Değişkenleri (UI için)
string g_stat_ema = "OFF";
string g_stat_adx = "OFF";
string g_stat_vwap= "OFF";

//==================================================================
// BÖLÜM 3: UI SINIFI
//==================================================================
class CDisplay {
private:
   void CreateRect(string name, int x, int y, int w, int h, color bg, color border) {
      string objName = UI_PREFIX + name;
      if(ObjectFind(0, objName) < 0) ObjectCreate(0, objName, OBJ_RECTANGLE_LABEL, 0, 0, 0);
      ObjectSetInteger(0, objName, OBJPROP_XDISTANCE, x);
      ObjectSetInteger(0, objName, OBJPROP_YDISTANCE, y);
      ObjectSetInteger(0, objName, OBJPROP_XSIZE, w);
      ObjectSetInteger(0, objName, OBJPROP_YSIZE, h);
      ObjectSetInteger(0, objName, OBJPROP_BGCOLOR, bg);
      ObjectSetInteger(0, objName, OBJPROP_BORDER_TYPE, BORDER_FLAT);
      ObjectSetInteger(0, objName, OBJPROP_COLOR, border);
      ObjectSetInteger(0, objName, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, objName, OBJPROP_SELECTABLE, false);
   }
   void CreateLabel(string name, string text, int x, int y, color c, int size=8, string font="Verdana", bool bold=false) {
      string objName = UI_PREFIX + name;
      if(ObjectFind(0, objName) < 0) ObjectCreate(0, objName, OBJ_LABEL, 0, 0, 0);
      ObjectSetInteger(0, objName, OBJPROP_XDISTANCE, x);
      ObjectSetInteger(0, objName, OBJPROP_YDISTANCE, y);
      ObjectSetString(0, objName, OBJPROP_TEXT, text);
      ObjectSetInteger(0, objName, OBJPROP_COLOR, c);
      ObjectSetInteger(0, objName, OBJPROP_FONTSIZE, size);
      ObjectSetString(0, objName, OBJPROP_FONT, bold ? font + " Bold" : font);
      ObjectSetInteger(0, objName, OBJPROP_CORNER, CORNER_LEFT_UPPER);
      ObjectSetInteger(0, objName, OBJPROP_SELECTABLE, false);
   }

public:
   void Init() {
      if(MQLInfoInteger(MQL_OPTIMIZATION)) return;

      CreateRect("MainBG", InpPanelX, InpPanelY, PANEL_W, PANEL_H, CLR_BG_MAIN, CLR_BORDER);
      CreateLabel("Header", "GOLD Grid Confidence v7.32 — Hibrit TP & Virtual", InpPanelX + 10, InpPanelY + 5, clrGray, 8, "Verdana");

      int y = InpPanelY + 25;
      int x_box = InpPanelX + 5;
      int box_w = PANEL_W - 10;
      int col1 = x_box + 10;
      int col2 = x_box + 200;

      CreateRect("Box_Signal", x_box, y, box_w, 120, CLR_BG_BOX, clrAqua); /// Değişiklik: Yükseklik 120 oldu
      CreateLabel("Val_Score",      "İç MS Skoru: 0.0",          col1, y + 10, clrWhite, 8, "Verdana", true);
      CreateLabel("Val_Thr",        "Eşikler (B/S): -- / --",    col1, y + 25, clrGold, 8);
      CreateLabel("Val_Prediction", "Son Durum: NÖTR",           col1, y + 40, clrWhite, 8);
      CreateLabel("Val_GridCount",  "Buy: 0 | Sell: 0",          col1, y + 55, clrWhite, 8);
      CreateLabel("Val_Profit",     "Yüzen K/Z: $0.00",          col1, y + 70, clrWhite, 8);
      CreateLabel("Val_VirtMode",   "Sanal Mod: OFF",            col1, y + 90, clrSilver, 8, "Verdana", true); /// Yeni

      CreateLabel("Val_Symbol",    _Symbol,                col2, y + 10, CLR_TEXT_VAL, 10, "Verdana", true);
      CreateLabel("Val_Time",      "00:00",                col2 + 80, y + 10, CLR_TEXT_VAL, 10, "Verdana", true);
      CreateLabel("Val_IndStatus", "Mod: Yükleniyor...",   col2, y + 30, CLR_ACTIVE, 8, "Verdana", true);
      CreateLabel("Val_Ping",      "Ping: 0 ms",           col2, y + 50, clrGray, 8);
      
      CreateLabel("Lbl_Filters",   "Aktif Filtreler:",       col2, y + 70, clrSilver, 8);
      CreateLabel("Val_FiltEma",   "EMA: OFF",               col2, y + 85, clrGray, 8);
      CreateLabel("Val_FiltAdx",   "ADX: OFF",               col2, y + 100, clrGray, 8);
      CreateLabel("Val_FiltVwap",  "VWAP: OFF",              col2 + 60, y + 85, clrGray, 8);

      y += 130; /// Değişiklik: Kaydırma artırıldı
      CreateLabel("Lbl_Risk", "GRİD & SEKANAS PARAMETRELERİ", x_box, y, CLR_TEXT_LBL, 8, "Verdana");
      y += 15;
      CreateRect("Box_Risk", x_box, y, box_w, 105, CLR_BG_BOX, CLR_BORDER);
      
      CreateLabel("Val_SkUnit",   "1 Sekanas: $0.0000",                   col1, y + 10, clrSilver, 8, "Verdana", true);
      CreateLabel("Val_BaseTP",   "Aktif TP: Yükleniyor",                 col1, y + 28, clrGold, 8, "Verdana", true);
      CreateLabel("Val_Baskets",  "Kapanan Sepet: 0",                     col1, y + 46, clrSilver, 8);
      CreateLabel("Val_DD",       "Drawdown: 0.0%",                       col1, y + 64, clrSilver, 8);
      CreateLabel("Val_Spread",   "Spread: $0.00",                        col1, y + 82, clrSilver, 8);

      CreateLabel("Val_Param1", StringFormat("Lot: %.2f | Step: %.2f", InpBaslangicLot, InpLotArtisi), col2, y + 10, CLR_ACCENT, 8, "Verdana", true);
      CreateLabel("Val_Param2", StringFormat("L0 Mes: %.1f Sk", InpL0IciMesafeSk), col2, y + 28, CLR_TEXT_VAL, 8);
      CreateLabel("Val_Param3", StringFormat("Major: %.1f Sk", InpAnaKademeMesafeSk), col2, y + 46, CLR_TEXT_VAL, 8);
      CreateLabel("Val_Param4", StringFormat("Max Kademe: %d", InpMaxGridKademe), col2, y + 64, CLR_TEXT_VAL, 8);
      CreateLabel("Val_Param5", StringFormat("Lot Tavan: %.1f", InpYondeMaxToplamLot), col2, y + 82, CLR_TEXT_VAL, 8);
   }

   void Update(int ping, double score, double b_thr, double s_thr, string prediction_str,
               double profit, int buy_cnt, int sell_cnt, double sk_unit,
               double dynamic_tp, double dd_pct, double spread) {
      if(MQLInfoInteger(MQL_OPTIMIZATION)) return;

      ObjectSetString(0, UI_PREFIX + "Val_Time", OBJPROP_TEXT, TimeToString(TimeCurrent(), TIME_MINUTES));
      ObjectSetString(0, UI_PREFIX + "Val_Ping", OBJPROP_TEXT, "Ping: " + (string)ping + " ms");
      ObjectSetString(0, UI_PREFIX + "Val_Score", OBJPROP_TEXT, StringFormat("İç MS Skoru: %.2f", score));
      ObjectSetString(0, UI_PREFIX + "Val_Thr", OBJPROP_TEXT, StringFormat("Eşikler (B/S): %.1f / %.1f", b_thr, s_thr));
      ObjectSetString(0, UI_PREFIX + "Val_Prediction", OBJPROP_TEXT, "Son Durum: " + prediction_str);
      ObjectSetString(0, UI_PREFIX + "Val_GridCount", OBJPROP_TEXT, StringFormat("Buy: %d | Sell: %d", buy_cnt, sell_cnt));
      
      color profColor = profit > 0 ? clrLime : (profit < 0 ? clrRed : clrWhite);
      ObjectSetString(0, UI_PREFIX + "Val_Profit", OBJPROP_TEXT, StringFormat("Yüzen K/Z: $%.2f", profit));
      ObjectSetInteger(0, UI_PREFIX + "Val_Profit", OBJPROP_COLOR, profColor);
      
      ObjectSetString(0, UI_PREFIX + "Val_SkUnit",  OBJPROP_TEXT, StringFormat("1 Sekanas: $%.4f", sk_unit));
      
      string tpModeStr = "";
      string tpValStr = "";
      if(InpTPStrategy == TP_VIRTUAL_DOLLAR) { tpModeStr = "Sanal TP ($)"; tpValStr = StringFormat("Hedef: $%.2f", dynamic_tp); }
      else if(InpTPStrategy == TP_VIRTUAL_SK) { tpModeStr = "Sanal TP (Sk)"; tpValStr = StringFormat("Hedef: $%.2f", dynamic_tp); }
      else if(InpTPStrategy == TP_PHYSICAL_AVERAGE) { tpModeStr = "Fiziksel (Ort)"; tpValStr = StringFormat("Fiziksel: %.1f Sk", InpPhysicalTPSk); }
      else if(InpTPStrategy == TP_PHYSICAL_INDIV) { tpModeStr = "Fiziksel (Tekil)"; tpValStr = StringFormat("Fiziksel: %.1f Sk", InpPhysicalTPSk); }

      ObjectSetString(0, UI_PREFIX + "Val_IndStatus", OBJPROP_TEXT, tpModeStr);
      ObjectSetString(0, UI_PREFIX + "Val_BaseTP",  OBJPROP_TEXT, tpValStr);
      
      ObjectSetString(0, UI_PREFIX + "Val_Baskets", OBJPROP_TEXT, "Kapanan Sepet: " + IntegerToString(g_total_baskets));
      ObjectSetString(0, UI_PREFIX + "Val_DD",      OBJPROP_TEXT, StringFormat("Drawdown: %.1f%%", dd_pct));
      ObjectSetString(0, UI_PREFIX + "Val_Spread",  OBJPROP_TEXT, StringFormat("Spread: $%.2f", spread));

      /// Değişiklik: Yeni Modüler Arayüz Güncellemeleri
      ObjectSetString(0, UI_PREFIX + "Val_VirtMode", OBJPROP_TEXT, InpUseVirtualTrading ? "Sanal Mod: AKTİF" : "Sanal Mod: OFF");
      ObjectSetInteger(0, UI_PREFIX + "Val_VirtMode", OBJPROP_COLOR, InpUseVirtualTrading ? clrOrange : clrSilver);

      ObjectSetString(0, UI_PREFIX + "Val_FiltEma", OBJPROP_TEXT, "EMA(M5): " + g_stat_ema);
      ObjectSetString(0, UI_PREFIX + "Val_FiltAdx", OBJPROP_TEXT, "ADX(M5): " + g_stat_adx);
      ObjectSetString(0, UI_PREFIX + "Val_FiltVwap", OBJPROP_TEXT, "VWAP: " + g_stat_vwap);
      
      ObjectSetInteger(0, UI_PREFIX + "Val_FiltEma", OBJPROP_COLOR, g_stat_ema == "OK" ? clrLime : (g_stat_ema == "OFF" ? clrGray : clrRed));
      ObjectSetInteger(0, UI_PREFIX + "Val_FiltAdx", OBJPROP_COLOR, g_stat_adx == "OK" ? clrLime : (g_stat_adx == "OFF" ? clrGray : clrRed));
      ObjectSetInteger(0, UI_PREFIX + "Val_FiltVwap", OBJPROP_COLOR, g_stat_vwap == "OK" ? clrLime : (g_stat_vwap == "OFF" ? clrGray : clrRed));
   }
};

CDisplay g_display;

//==================================================================
// BÖLÜM 4: INIT / DEINIT
//==================================================================
int OnInit()
{
   g_trade_buy.SetExpertMagicNumber(InpAlisMagic);
   g_trade_buy.SetDeviationInPoints(InpSlippage);
   g_trade_sell.SetExpertMagicNumber(InpSatisMagic);
   g_trade_sell.SetDeviationInPoints(InpSlippage);

   // Core Confidence Indikatörleri
   g_handle_ema20 = iMA(_Symbol, PERIOD_H1, 20, 0, MODE_EMA, PRICE_CLOSE);
   g_handle_ema50 = iMA(_Symbol, PERIOD_H1, 50, 0, MODE_EMA, PRICE_CLOSE);
   g_handle_rsi14 = iRSI(_Symbol, PERIOD_H1, 14, PRICE_CLOSE);
   g_handle_atr5  = iATR(_Symbol, PERIOD_H1, 5);

   // Yeni Eklenen Filtre İndikatörleri (M5)
   if(InpUseMartiEma) {
      g_handle_m5_emaFast = iMA(_Symbol, PERIOD_M5, InpEmaFastPeriod, 0, MODE_EMA, PRICE_CLOSE);
      g_handle_m5_emaSlow = iMA(_Symbol, PERIOD_M5, InpEmaSlowPeriod, 0, MODE_EMA, PRICE_CLOSE);
   }
   if(InpUseAdxFilter) {
      g_handle_m5_adx = iADX(_Symbol, PERIOD_M5, InpAdxPeriod);
   }

   if(g_handle_ema20 == INVALID_HANDLE || g_handle_ema50 == INVALID_HANDLE || g_handle_rsi14 == INVALID_HANDLE || g_handle_atr5 == INVALID_HANDLE) {
      Print("HATA: Temel MT5 indikatörleri yüklenemedi.");
      return INIT_FAILED;
   }

   g_account_peak_equity = AccountInfoDouble(ACCOUNT_EQUITY);
   g_dynamic_basetp = 0.0;
   g_display.Init();
   
   Print("=== GOLD_Grid_Confidence v7.32 Hibrit & Virtual Başlatıldı ===");
   return INIT_SUCCEEDED;
}

void OnDeinit(const int reason)
{
   IndicatorRelease(g_handle_ema20);
   IndicatorRelease(g_handle_ema50);
   IndicatorRelease(g_handle_rsi14);
   IndicatorRelease(g_handle_atr5);
   
   if(g_handle_m5_emaFast != INVALID_HANDLE) IndicatorRelease(g_handle_m5_emaFast);
   if(g_handle_m5_emaSlow != INVALID_HANDLE) IndicatorRelease(g_handle_m5_emaSlow);
   if(g_handle_m5_adx != INVALID_HANDLE) IndicatorRelease(g_handle_m5_adx);

   ObjectsDeleteAll(0, UI_PREFIX);
}

//==================================================================
// BÖLÜM 5: YARDIMCI / RİSK FONKSİYONLARI
//==================================================================
double GetSekanasUnit() { return SymbolInfoDouble(_Symbol, SYMBOL_BID) / 10000.0; }

double GetSpreadDollars() {
   double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
   return (ask - bid);
}

/// Değişiklik: CalculateDailyVWAP M5 tabanlı VWAP hesaplaması eklendi
double CalculateDailyVWAP() {
   datetime todayStart = iTime(_Symbol, PERIOD_D1, 0);
   int shift = iBarShift(_Symbol, PERIOD_M5, todayStart);
   if(shift < 0) return 0.0;
   
   double sumPV = 0.0;
   double sumV  = 0.0;
   
   for(int i = 0; i <= MathMin(shift, 200); i++) {
      double h = iHigh(_Symbol, PERIOD_M5, i);
      double l = iLow(_Symbol, PERIOD_M5, i);
      double c = iClose(_Symbol, PERIOD_M5, i);
      double v = (double)iTickVolume(_Symbol, PERIOD_M5, i);
      
      double typicalPrice = (h + l + c) / 3.0;
      sumPV += (typicalPrice * v);
      sumV  += v;
   }
   
   if(sumV == 0.0) return 0.0;
   return sumPV / sumV;
}

double GetDrawdownPercent() {
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity > g_account_peak_equity) g_account_peak_equity = equity;
   if(g_account_peak_equity <= 0) return 0.0;
   double dd = (1.0 - equity / g_account_peak_equity) * 100.0;
   return MathMax(0.0, dd);
}

//==================================================================
// BÖLÜM 6: SANAL (VIRTUAL) ve GERÇEK İŞLEM SOYUTLAMA (ABSTRACTION)
//==================================================================
/// Değişiklik: Pozisyon Sayımı ve Kar Hesaplaması Sanal Moda Uyarlandı

int GetActivePositionCount(int magic) {
   if(!InpUseVirtualTrading) {
      int count = 0;
      for(int i = PositionsTotal() - 1; i >= 0; i--) {
         if(PositionSelectByTicket(PositionGetTicket(i))) {
            if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == magic) count++;
         }
      }
      return count;
   } else {
      int count = 0;
      for(int i = 0; i < g_vCount; i++) {
         if(g_vPos[i].isActive && g_vPos[i].magic == magic) count++;
      }
      return count;
   }
}

double GetActiveTotalLots(int magic) {
   double lots = 0.0;
   if(!InpUseVirtualTrading) {
      for(int i = PositionsTotal() - 1; i >= 0; i--) {
         if(PositionSelectByTicket(PositionGetTicket(i))) {
            if(PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == magic) lots += PositionGetDouble(POSITION_VOLUME);
         }
      }
   } else {
      for(int i = 0; i < g_vCount; i++) {
         if(g_vPos[i].isActive && g_vPos[i].magic == magic) lots += g_vPos[i].volume;
      }
   }
   return lots;
}

double GetActiveLastPrice(int magic) {
   double lastP = 0;
   if(!InpUseVirtualTrading) {
      ulong lastT = 0;
      for(int i = PositionsTotal() - 1; i >= 0; i--) {
         ulong ticket = PositionGetTicket(i);
         if(PositionSelectByTicket(ticket)) {
            if(PositionGetInteger(POSITION_MAGIC) == magic && ticket > lastT) {
               lastT = ticket;
               lastP = PositionGetDouble(POSITION_PRICE_OPEN);
            }
         }
      }
   } else {
      datetime lastT = 0;
      for(int i = 0; i < g_vCount; i++) {
         if(g_vPos[i].isActive && g_vPos[i].magic == magic && g_vPos[i].openTime > lastT) {
            lastT = g_vPos[i].openTime;
            lastP = g_vPos[i].openPrice;
         }
      }
   }
   return lastP;
}

double GetActiveBasketProfit(int magic) {
   double profit = 0;
   if(!InpUseVirtualTrading) {
      for(int i = PositionsTotal() - 1; i >= 0; i--) {
         if(PositionSelectByTicket(PositionGetTicket(i)) && PositionGetInteger(POSITION_MAGIC) == magic && PositionGetString(POSITION_SYMBOL) == _Symbol) {
            profit += PositionGetDouble(POSITION_PROFIT) + PositionGetDouble(POSITION_SWAP);
         }
      }
   } else {
      double cSz = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
      double bid = SymbolInfoDouble(_Symbol, SYMBOL_BID);
      double ask = SymbolInfoDouble(_Symbol, SYMBOL_ASK);
      
      for(int i = 0; i < g_vCount; i++) {
         if(g_vPos[i].isActive && g_vPos[i].magic == magic) {
            double diff = (g_vPos[i].type == 0) ? bid - g_vPos[i].openPrice : g_vPos[i].openPrice - ask;
            profit += diff * g_vPos[i].volume * cSz;
         }
      }
   }
   return profit;
}

void CloseActiveBasket(int magic, string reason="Hedef TP") {
   // Gerçek Pozisyonları Kapat (Sanal modda oluşturulmuş gerçek pozisyonlar dahil)
   for(int i = PositionsTotal() - 1; i >= 0; i--) {
      ulong ticket = PositionGetTicket(i);
      if(PositionSelectByTicket(ticket) && PositionGetString(POSITION_SYMBOL) == _Symbol && PositionGetInteger(POSITION_MAGIC) == magic) {
         if(PositionGetInteger(POSITION_TYPE) == POSITION_TYPE_BUY) g_trade_buy.PositionClose(ticket);
         else g_trade_sell.PositionClose(ticket);
      }
   }
   
   // Sanal Pozisyonları Kapat
   if(InpUseVirtualTrading) {
      for(int i = 0; i < g_vCount; i++) {
         if(g_vPos[i].isActive && g_vPos[i].magic == magic) {
            g_vPos[i].isActive = false;
         }
      }
   }
   
   if(GetActivePositionCount(magic) == 0) {
      g_total_baskets++;
   }
}

void ExecuteActiveTrade(ENUM_SIGNAL sig, double lot, double currentPrice, double sl, double tp, string tag) {
   int magic = (sig == SIGNAL_BUY) ? InpAlisMagic : InpSatisMagic;
   
   if(!InpUseVirtualTrading) {
      bool ok = (sig == SIGNAL_BUY)
                ? g_trade_buy.Buy(lot,  _Symbol, currentPrice, sl, tp, tag)
                : g_trade_sell.Sell(lot, _Symbol, currentPrice, sl, tp, tag);
      if(ok) g_lastOrderTimeMs = GetTickCount();
   } else {
      // Sanal Pozisyon Kaydı
      int idx = -1;
      for(int i = 0; i < g_vCount; i++) { if(!g_vPos[i].isActive) { idx = i; break; } }
      if(idx == -1) {
         if(g_vCount >= MAX_VIRTUAL_POS) { Print("HATA: Sanal dizi dolu!"); return; }
         idx = g_vCount++;
      }
      
      bool doReal = (lot >= InpVirtualThreshold);
      
      g_vPos[idx].magic = magic;
      g_vPos[idx].type = (sig == SIGNAL_BUY) ? 0 : 1;
      g_vPos[idx].openPrice = currentPrice;
      g_vPos[idx].volume = lot;
      g_vPos[idx].openTime = TimeCurrent();
      g_vPos[idx].isActive = true;
      g_vPos[idx].isRealSpawned = doReal;
      
      // Eşik geçilmişse Gerçek MT5 İşlemi Gönder
      if(doReal) {
         double rL = NormalizeDouble(lot * InpRealLotMultiplier, 2);
         double step = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
         double minL = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
         rL = MathMax(MathFloor(rL/step)*step, minL); // Lot düzeltmesi
         
         bool ok = (sig == SIGNAL_BUY)
                   ? g_trade_buy.Buy(rL,  _Symbol, currentPrice, sl, tp, tag + "_REAL")
                   : g_trade_sell.Sell(rL, _Symbol, currentPrice, sl, tp, tag + "_REAL");
         if(ok) g_lastOrderTimeMs = GetTickCount();
      }
      PrintFormat("[V-OPEN] %s | Lot: %.2f | Gerçek İletim: %s", tag, lot, doReal ? "EVET" : "HAYIR");
   }
}

bool CheckAdverseDistanceActive(int magic, bool isMajorLevel, double spacingMult = 1.0) {
   int count = GetActivePositionCount(magic);
   if(count == 0) return true;
   double lastPrice = GetActiveLastPrice(magic);
   if(lastPrice <= 0) return false;

   double currentPrice = (magic == InpAlisMagic) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   double diff = (magic == InpAlisMagic) ? (lastPrice - currentPrice) : (currentPrice - lastPrice);
   if(diff <= 0) return false;

   double sk = GetSekanasUnit();
   double atr[1] = {0.0};
   if(CopyBuffer(g_handle_atr5, 0, 0, 1, atr) <= 0) return false;

   double reqDist;
   if(isMajorLevel) reqDist = (InpAnaKademeMesafeSk * sk + atr[0] * InpAnaKademeAtrCarpan) * spacingMult;
   else reqDist = (InpL0IciMesafeSk * sk + atr[0] * InpL0AtrCarpan) * spacingMult;
   
   return (diff >= reqDist);
}

//==================================================================
// BÖLÜM 7: SEPET YÖNETİMİ HİBRİT MANTIĞI
//==================================================================
double GetFixedDollarTarget(int magic) {
   int count = GetActivePositionCount(magic);
   if(count == 0) return 0.0;
   int majorLvl = (count - 1) / InpKademeBasinaTekrar;
   double target = InpSabitDolarTP + (majorLvl * InpMajorBonus);
   if(target > InpMaxSabitTP) target = InpMaxSabitTP;
   return target;
}

double GetSkBasedTPTargetDollars(int magic) {
   int count = GetActivePositionCount(magic);
   if(count == 0) return 0.0;
   double totalLots = GetActiveTotalLots(magic);
   double excessLot = totalLots - InpBaslangicLot;
   if(excessLot < 0) excessLot = 0.0;
   
   double dropSteps = MathRound(excessLot / InpLotStepForDrop);
   double currentTargetSk = InpBaseTPSk - (dropSteps * InpDropPerLotStepSk);
   if(currentTargetSk < InpMinTPSk) currentTargetSk = InpMinTPSk;

   double skPriceMove = GetSekanasUnit();
   double contractSize = SymbolInfoDouble(_Symbol, SYMBOL_TRADE_CONTRACT_SIZE);
   return currentTargetSk * skPriceMove * contractSize * totalLots;
}

double GetActiveTPTarget(int magic) {
   if(InpTPStrategy == TP_VIRTUAL_DOLLAR) return GetFixedDollarTarget(magic);
   else if(InpTPStrategy == TP_VIRTUAL_SK) return GetSkBasedTPTargetDollars(magic);
   return 0.0; 
}

void ManageBasket(int magic)
{
   int count = GetActivePositionCount(magic);
   if(count == 0) return;
   
   double profit = GetActiveBasketProfit(magic);
   
   if(InpTPStrategy == TP_VIRTUAL_DOLLAR || InpTPStrategy == TP_VIRTUAL_SK) {
       double targetTP = GetActiveTPTarget(magic);
       if(profit >= targetTP) {
          string reason = StringFormat("Sanal TP Hedefi ($%.2f, %d poz)", targetTP, count);
          CloseActiveBasket(magic, reason);
       }
   }
   // Physical trailing ignores virtual structure and protects only MT5 real trades.
}

//==================================================================
// BÖLÜM 8: GÜVENLİK KONTROLLERİ VE SİNYAL (FİLTRELİ)
//==================================================================
bool SafetyChecksPass() {
   double equity = AccountInfoDouble(ACCOUNT_EQUITY);
   if(equity < InpMinEquity) return false;
   if(GetDrawdownPercent() >= InpMaxDrawdownYuzde) return false;
   if(GetSpreadDollars() > InpMaxSpreadDolar) return false;
   ulong now = GetTickCount();
   if(now - g_lastOrderTimeMs < (ulong)InpEmirGecikmeMs) return false;
   return true;
}

double CalculateInternalConfidence() {
   double score = 0.0;
   double ema20[1], ema50[1], rsi[1], close[1];
   double high[5], low[5];

   if(CopyBuffer(g_handle_ema20, 0, 0, 1, ema20) <= 0) return 0.0;
   if(CopyBuffer(g_handle_ema50, 0, 0, 1, ema50) <= 0) return 0.0;
   if(CopyBuffer(g_handle_rsi14, 0, 0, 1, rsi) <= 0) return 0.0;
   if(CopyClose(_Symbol, PERIOD_H1, 0, 1, close) <= 0) return 0.0;
   if(CopyHigh(_Symbol, PERIOD_H1, 1, 5, high) <= 0) return 0.0;
   if(CopyLow(_Symbol, PERIOD_H1, 1, 5, low) <= 0) return 0.0;

   if(ema20[0] > ema50[0]) score += 30.0; else if(ema20[0] < ema50[0]) score -= 30.0;
   if(rsi[0] > 65.0) score += 30.0; else if(rsi[0] > 55.0) score += 15.0; else if(rsi[0] < 35.0) score -= 30.0; else if(rsi[0] < 45.0) score -= 15.0;

   double recentHigh = high[ArrayMaximum(high)];
   double recentLow  = low[ArrayMinimum(low)];

   if(close[0] > recentHigh) score += 40.0; else if(close[0] < recentLow) score -= 40.0;
   else { if(close[0] > (recentHigh + recentLow) / 2.0) score += 10.0; else score -= 10.0; }

   if(score >  100.0) score =  100.0; if(score < -100.0) score = -100.0;
   return score;
}

/// Değişiklik: GetConfidenceSignal içerisine M5 Trend Filtreleri entegre edildi
ENUM_SIGNAL GetConfidenceSignal() {
   g_last_confidence = CalculateInternalConfidence();
   double buyProfit  = GetActiveBasketProfit(InpAlisMagic);
   double sellProfit = GetActiveBasketProfit(InpSatisMagic);

   g_active_buy_thr  = (sellProfit < 0) ?  InpYumusatilmisEsik :  InpNormalEsik;
   g_active_sell_thr = (buyProfit  < 0) ? -InpYumusatilmisEsik : -InpNormalEsik;

   ENUM_SIGNAL rawSignal = SIGNAL_NONE;
   if(g_last_confidence >= g_active_buy_thr) rawSignal = SIGNAL_BUY;
   else if(g_last_confidence <= g_active_sell_thr) rawSignal = SIGNAL_SELL;

   // Marti M5 Filtreleri
   bool filterOkBuy = true;
   bool filterOkSell = true;
   
   if(InpUseMartiEma) {
      double ef[3], es[3];
      if(CopyBuffer(g_handle_m5_emaFast, 0, 0, 3, ef) > 0 && CopyBuffer(g_handle_m5_emaSlow, 0, 0, 3, es) > 0) {
         bool isEmaBuy  = (ef[1] > es[1]) && (ef[2] <= es[2]);
         bool isEmaSell = (ef[1] < es[1]) && (ef[2] >= es[2]);
         if(!isEmaBuy) filterOkBuy = false;
         if(!isEmaSell) filterOkSell = false;
         g_stat_ema = (isEmaBuy || isEmaSell) ? "OK" : "NOK";
      }
   } else { g_stat_ema = "OFF"; }

   if(InpUseAdxFilter) {
      double adx[1];
      if(CopyBuffer(g_handle_m5_adx, 0, 0, 1, adx) > 0) {
         if(adx[0] < InpAdxMinLevel) { filterOkBuy = false; filterOkSell = false; g_stat_adx = "NOK"; }
         else { g_stat_adx = "OK"; }
      }
   } else { g_stat_adx = "OFF"; }

   if(InpUseVwapFilter) {
      double vwap = CalculateDailyVWAP();
      double px = iClose(_Symbol, PERIOD_M5, 0);
      if(vwap > 0) {
         if(px < vwap) filterOkBuy = false;
         if(px > vwap) filterOkSell = false;
         g_stat_vwap = "OK";
      } else { g_stat_vwap = "NOK"; }
   } else { g_stat_vwap = "OFF"; }

   if(rawSignal == SIGNAL_BUY && filterOkBuy) { g_last_prediction_str = "BUY (FİLTRELİ)"; return SIGNAL_BUY; }
   if(rawSignal == SIGNAL_SELL && filterOkSell) { g_last_prediction_str = "SELL (FİLTRELİ)"; return SIGNAL_SELL; }

   g_last_prediction_str = "NÖTR";
   return SIGNAL_NONE;
}

//==================================================================
// BÖLÜM 9: GRID AÇILIŞ MANTIĞI
//==================================================================
double CalculateNextLot(int level) {
   if(level >= InpMaxGridKademe) return 0.0;
   double lot = InpBaslangicLot + (level * InpLotArtisi);
   double minLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MIN);
   double maxLot  = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_MAX);
   double stepLot = SymbolInfoDouble(_Symbol, SYMBOL_VOLUME_STEP);
   lot = MathMax(minLot, MathMin(maxLot, MathRound(lot / stepLot) * stepLot));
   return lot;
}

bool CanAddToSide(int magic, double newLot, int currentMajorLevel) {
   if(currentMajorLevel >= InpMaxGridKademe) return false;
   double currentTotal = GetActiveTotalLots(magic);
   if(currentTotal + newLot > InpYondeMaxToplamLot) return false;
   return true;
}

void TryFirstEntry(ENUM_SIGNAL sig) {
   if(sig == SIGNAL_NONE) return;
   if(!SafetyChecksPass()) return;
   int magic = (sig == SIGNAL_BUY) ? InpAlisMagic : InpSatisMagic;
   string sideTag = (sig == SIGNAL_BUY) ? "BUY" : "SELL";
   if(GetActivePositionCount(magic) > 0) return; 

   double lot = CalculateNextLot(0);
   if(lot <= 0.0) return;
   if(!CanAddToSide(magic, lot, 0)) return;
   
   double currentPrice = (sig == SIGNAL_BUY) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   ENUM_POSITION_TYPE type = (sig == SIGNAL_BUY) ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
   
   double sl = 0; // İlk giriş SL hesabı varsa buraya entegre edilir
   double tp = 0;

   string tag = sideTag + "_L0_1"; 
   ExecuteActiveTrade(sig, lot, currentPrice, sl, tp, tag);
}

void TryGridAddSide(int magic) {
   int total_cnt = GetActivePositionCount(magic);
   if(total_cnt == 0) return;  
   if(!SafetyChecksPass()) return;
   
   if(InpGridEklemeSinyalIster) {
      ENUM_SIGNAL curSig = GetConfidenceSignal();
      if(magic == InpAlisMagic  && curSig != SIGNAL_BUY)  return;
      if(magic == InpSatisMagic && curSig != SIGNAL_SELL) return;
   }

   string sideTag = (magic == InpAlisMagic) ? "BUY" : "SELL";
   bool isLosingSide = (GetActiveBasketProfit(magic) < 0);
   double spacingMult = isLosingSide ? InpKayipTarafSpacingCarpan : 1.0;

   double currentPrice = (magic == InpAlisMagic) ? SymbolInfoDouble(_Symbol, SYMBOL_ASK) : SymbolInfoDouble(_Symbol, SYMBOL_BID);
   bool isMajorStep = (total_cnt % InpKademeBasinaTekrar == 0);
   
   if(!CheckAdverseDistanceActive(magic, isMajorStep, spacingMult)) return;

   int level = total_cnt / InpKademeBasinaTekrar;
   double lot = CalculateNextLot(level);
   if(lot <= 0.0) return;
   if(!CanAddToSide(magic, lot, level)) return;

   ENUM_POSITION_TYPE type = (magic == InpAlisMagic) ? POSITION_TYPE_BUY : POSITION_TYPE_SELL;
   double sl = 0;
   double tp = 0;

   int innerIndex = (total_cnt % InpKademeBasinaTekrar) + 1;
   string tag = sideTag + "_L" + IntegerToString(level) + "_" + IntegerToString(innerIndex);
   
   ENUM_SIGNAL reqSig = (magic == InpAlisMagic) ? SIGNAL_BUY : SIGNAL_SELL;
   ExecuteActiveTrade(reqSig, lot, currentPrice, sl, tp, tag);
}

//==================================================================
// BÖLÜM 10: ON TICK
//==================================================================
void OnTick()
{
   static ulong last_tick = 0;
   ulong current_tick = GetTickCount();
   int ping = (int)(current_tick - last_tick);
   if(ping > 10000) ping = 0;
   last_tick = current_tick;

   ManageBasket(InpAlisMagic);
   ManageBasket(InpSatisMagic);

   TryGridAddSide(InpAlisMagic);
   TryGridAddSide(InpSatisMagic);
   
   ENUM_SIGNAL sig = GetConfidenceSignal();
   TryFirstEntry(sig);

   int b_cnt = GetActivePositionCount(InpAlisMagic);
   int s_cnt = GetActivePositionCount(InpSatisMagic);
   double totalFloating = GetActiveBasketProfit(InpAlisMagic) + GetActiveBasketProfit(InpSatisMagic);
   double dd = GetDrawdownPercent();
   double spread = GetSpreadDollars();

   double buyTarget  = GetActiveTPTarget(InpAlisMagic);
   double sellTarget = GetActiveTPTarget(InpSatisMagic);
   g_dynamic_basetp = MathMax(buyTarget, sellTarget);
   if(g_dynamic_basetp == 0) g_dynamic_basetp = InpSabitDolarTP;
   
   g_display.Update(ping, g_last_confidence, g_active_buy_thr, g_active_sell_thr,
                    g_last_prediction_str, totalFloating, b_cnt, s_cnt,
                    GetSekanasUnit(), g_dynamic_basetp, dd, spread);
}
//+------------------------------------------------------------------+