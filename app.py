import streamlit as st
import yfinance as yf
import pandas as pd
import requests

# ページの設定
st.set_page_config(page_title="米国株 AI分析ツール", page_icon="📊", layout="wide")
st.title("📊 米国株 AI分析ツール")
st.markdown("指定した銘柄の最新データを取得し、AIアナリストが投資レポートを作成します。")

# --- サイドバー (入力画面) ---
st.sidebar.header("⚙️ 設定")
api_key = st.sidebar.text_input("Gemini APIキー", type="password", help="あなたのAPIキーを入力してください")
ticker_symbol = st.sidebar.text_input("ティッカーシンボル", value="PINS", help="例: PINS, AAPL, NVDA").upper()
analyze_button = st.sidebar.button("分析を開始")

# --- 分析処理 ---
if analyze_button:
    if not api_key:
        st.warning("⚠️ サイドバーにGemini APIキーを入力してください。")
    elif not ticker_symbol:
        st.warning("⚠️ ティッカーシンボルを入力してください。")
    else:
        with st.spinner(f"📊 {ticker_symbol} のデータを取得・分析中...（約10〜20秒かかります）"):
            try:
                # データの取得
                ticker_data = yf.Ticker(ticker_symbol)

                # 決算発表日の取得
                try:
                    calendar = ticker_data.calendar
                    if isinstance(calendar, dict) and 'Earnings Date' in calendar:
                        earnings_date = calendar['Earnings Date'][0].strftime('%Y年%m月%d日')
                    else:
                        earnings_date = "未定・取得不可"
                except Exception:
                    earnings_date = "未定・取得不可"

                # 会社情報
                info = ticker_data.info
                summary = info.get('longBusinessSummary', '概要データなし')
                sector = info.get('sector', 'データなし')
                industry = info.get('industry', 'データなし')

                # 出来高とテクニカル指標
                hist = ticker_data.history(period="100d")
                if hist.empty:
                    st.error("❌ 株価データが取得できませんでした。")
                    st.stop()

                latest_volume = hist['Volume'].iloc[-1]
                avg_volume = hist['Volume'].mean()
                volume_status = "活発（注目度が高い）" if latest_volume > avg_volume else "平常通り"

                def calculate_rsi(data, window=14):
                    delta = data['Close'].diff()
                    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
                    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()
                    rs = gain / loss
                    return 100 - (100 / (1 + rs))

                hist['RSI'] = calculate_rsi(hist)
                latest_rsi = hist['RSI'].iloc[-1]
                hist['MA50'] = hist['Close'].rolling(window=50).mean()
                hist['MA200'] = hist['Close'].rolling(window=200).mean()
                latest_price = hist['Close'].iloc[-1]
                ma50 = hist['MA50'].iloc[-1]
                ma200 = hist['MA200'].iloc[-1]
                trend_status = "上昇トレンド" if latest_price > ma200 else "下落トレンド"

                tech_data = f"""
                ・現在の株価: ${latest_price:.2f}
                ・50日移動平均線: ${ma50:.2f}
                ・200日移動平均線: ${ma200:.2f}
                ・長期トレンド判定: {trend_status}
                ・直近のRSI: {latest_rsi:.1f}%
                """

                # 財務データ
                rev_growth = info.get('revenueGrowth')
                op_margin = info.get('operatingMargins')
                roe = info.get('returnOnEquity')
                rev_str = f"{rev_growth * 100:.1f}%" if rev_growth else "データなし"
                margin_str = f"{op_margin * 100:.1f}%" if op_margin else "データなし"
                roe_str = f"{roe * 100:.1f}%" if roe else "データなし"
                debt_eq = info.get('debtToEquity')
                debt_str = f"{debt_eq}%" if debt_eq is not None else "データなし"
                forward_pe = info.get('forwardPE')
                pe_str = f"{forward_pe:.1f} 倍" if forward_pe is not None else "データなし"
                op_cashflow = info.get('operatingCashflow')
                cf_str = f"${op_cashflow:,.0f}" if op_cashflow is not None else "データなし"
                peg_ratio = info.get('pegRatio')
                peg_str = f"{peg_ratio:.2f}" if peg_ratio is not None else "データなし"

                financial_data = f"""
                ・売上高成長率: {rev_str}
                ・営業利益率: {margin_str}
                ・ROE（自己資本利益率）: {roe_str}
                ・負債自己資本比率 (D/Eレシオ): {debt_str}
                ・予想PER (Forward PE): {pe_str}
                ・PEGレシオ (成長率を加味したPER): {peg_str}
                ・営業キャッシュフロー: {cf_str}
                """

                # ニュース
                news_list = ticker_data.news[:3]
                news_text = ""
                for item in news_list:
                    title = item.get('content', {}).get('title') or item.get('title', 'タイトル不明')
                    news_text += f"・タイトル: {title}\n"

                # プロンプト作成
                prompt = f"""
                あなたはウォール街で長年の経験を持つ、投資家教育のプロである米国株アナリストAIです。
                以下の【提供データ】を分析し、投資家が「今すぐどう動くべきか」を判断できるレポートを作成してください。

                ### 【提供データ】
                ■ 銘柄情報: {ticker_symbol}
                ■ 次回決算発表予定日: {earnings_date}
                ■ 会社概要: {summary}
                ■ セクター・業界: {sector} / {industry}
                ■ 現在の株価: ${latest_price:.2f} (出来高: {latest_volume:,} / 状態: {volume_status})
                ■ テクニカル: {tech_data}
                ■ 財務データ: {financial_data}
                ■ ニュース: {news_text}

                ---

                ### 【出力フォーマット】
                # 📊 【{ticker_symbol}】最新投資分析レポート
                ## 💡 総合判定
                * **【長期保有の適性】**：[◎ / 〇 / △ / ×] と理由
                * **【今すぐ買うべき？】**：[買うべき / 様子見 / 待機] と理由
                * **【買い時の目安価格】**：妥当な価格とその理由
                * **AIのコーチング**：結論に至った最大の理由を1〜2文で

                ## 1. 🏢 企業情報と出来高分析
                ## 2. 📰 ニュース感情分析
                ## 3. 📈 チャートの状況
                ## 4. 🏢 企業の体力チェック
                ## 5. 🏁 まとめ（投資家への提言）
                """

                # Gemini API呼び出し
                url_generate = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
                headers = {'Content-Type': 'application/json'}
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                res_gen = requests.post(url_generate, headers=headers, json=payload)
                res_data = res_gen.json()

                # 結果の表示
                if 'candidates' in res_data:
                    report_content = res_data['candidates'][0]['content']['parts'][0]['text']
                    st.success("✨ 分析が完了しました！")
                    st.markdown("---")
                    st.markdown(report_content)
                else:
                    st.error("⚠️ 分析の生成に失敗しました。APIキーが正しいか確認してください。")
                    st.json(res_data)

            except Exception as e:
                st.error(f"予期せぬエラーが発生しました: {e}")