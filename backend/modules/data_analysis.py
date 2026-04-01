"""
Data Analysis Module - CSV Analysis with Gemini Insights
=========================================================
CSV files ko Pandas se analyze karo aur Google Gemini se insights lo.
"""

import google.generativeai as genai
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import io
import base64
import asyncio
import json


class DataAnalysisModule:

    def __init__(self, api_key: str, model_name: str = "gemini-2.0-flash"):
        genai.configure(api_key=api_key)
        self.model_name = model_name

    def _load_csv(self, csv_bytes: bytes) -> pd.DataFrame:
        csv_io = io.BytesIO(csv_bytes)
        for encoding in ['utf-8', 'latin-1', 'iso-8859-1', 'cp1252']:
            try:
                csv_io.seek(0)
                return pd.read_csv(csv_io, encoding=encoding)
            except (UnicodeDecodeError, pd.errors.ParserError):
                continue
        raise ValueError("❌ CSV file read nahi ho saka.")

    def _get_statistical_summary(self, df: pd.DataFrame) -> dict:
        summary = {
            "shape": {"rows": df.shape[0], "columns": df.shape[1]},
            "columns": list(df.columns),
            "dtypes": df.dtypes.astype(str).to_dict(),
            "null_counts": df.isnull().sum().to_dict(),
            "null_percentage": (df.isnull().sum() / len(df) * 100).round(2).to_dict(),
        }
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        if numeric_cols:
            summary["numeric_stats"] = df[numeric_cols].describe().to_dict()

        cat_cols = df.select_dtypes(include=['object']).columns.tolist()
        cat_summary = {}
        for col in cat_cols[:10]:
            value_counts = df[col].value_counts().head(10)
            cat_summary[col] = {
                "unique_values": df[col].nunique(),
                "top_values": value_counts.to_dict()
            }
        summary["categorical_stats"] = cat_summary
        summary["sample_data"] = df.head(5).to_dict(orient='records')
        return summary

    def _generate_chart(self, df: pd.DataFrame) -> str:
        try:
            plt.style.use('seaborn-v0_8-darkgrid')
        except OSError:
            try:
                plt.style.use('seaborn-darkgrid')
            except OSError:
                plt.style.use('ggplot')

        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        fig.suptitle('Data Analysis Dashboard', fontsize=16, fontweight='bold')

        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        cat_cols = df.select_dtypes(include=['object']).columns.tolist()
        colors = ['#2196F3', '#4CAF50', '#FF9800', '#E91E63']

        ax1 = axes[0, 0]
        if numeric_cols:
            col = numeric_cols[0]
            ax1.hist(df[col].dropna(), bins=20, color=colors[0], alpha=0.8, edgecolor='white')
            ax1.set_title(f'Distribution: {col}', fontweight='bold')
            ax1.set_xlabel(col)
            ax1.set_ylabel('Frequency')
        else:
            ax1.text(0.5, 0.5, 'No numeric data', ha='center', va='center', transform=ax1.transAxes)

        ax2 = axes[0, 1]
        if cat_cols:
            col = cat_cols[0]
            top_vals = df[col].value_counts().head(8)
            ax2.bar(range(len(top_vals)), top_vals.values, color=colors[1], alpha=0.8)
            ax2.set_title(f'Top Values: {col}', fontweight='bold')
            ax2.set_xticks(range(len(top_vals)))
            ax2.set_xticklabels(list(top_vals.index), rotation=45, ha='right', fontsize=8)
            ax2.set_ylabel('Count')
        else:
            ax2.text(0.5, 0.5, 'No categorical data', ha='center', va='center', transform=ax2.transAxes)

        ax3 = axes[1, 0]
        null_data = df.isnull().sum()
        null_data = null_data[null_data > 0]
        if len(null_data) > 0:
            ax3.barh(list(null_data.index), null_data.values, color=colors[2], alpha=0.8)
            ax3.set_title('Missing Values', fontweight='bold')
            ax3.set_xlabel('Count')
        else:
            ax3.text(0.5, 0.5, '✅ No Missing Values!', ha='center', va='center',
                    fontsize=14, color='green', fontweight='bold', transform=ax3.transAxes)
            ax3.set_title('Missing Values', fontweight='bold')

        ax4 = axes[1, 1]
        if len(numeric_cols) >= 2:
            corr_cols = numeric_cols[:6]
            corr_matrix = df[corr_cols].corr()
            im = ax4.imshow(corr_matrix.values, cmap='RdBu_r', aspect='auto', vmin=-1, vmax=1)
            ax4.set_xticks(range(len(corr_cols)))
            ax4.set_yticks(range(len(corr_cols)))
            ax4.set_xticklabels(corr_cols, rotation=45, ha='right', fontsize=8)
            ax4.set_yticklabels(corr_cols, fontsize=8)
            plt.colorbar(im, ax=ax4, shrink=0.8)
            ax4.set_title('Correlation Matrix', fontweight='bold')
            for i in range(len(corr_matrix)):
                for j in range(len(corr_matrix.columns)):
                    ax4.text(j, i, f'{corr_matrix.iloc[i, j]:.2f}', ha='center', va='center', fontsize=7)
        elif len(numeric_cols) == 1:
            col = numeric_cols[0]
            ax4.boxplot(df[col].dropna(), patch_artist=True, boxprops=dict(facecolor=colors[3], alpha=0.7))
            ax4.set_title(f'Box Plot: {col}', fontweight='bold')
        else:
            ax4.text(0.5, 0.5, 'Insufficient data', ha='center', va='center', transform=ax4.transAxes)

        plt.tight_layout()
        buf = io.BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        chart_b64 = base64.b64encode(buf.read()).decode('utf-8')
        plt.close('all')
        return chart_b64

    async def analyze(self, csv_bytes: bytes, question: str) -> dict:
        df = await asyncio.to_thread(self._load_csv, csv_bytes)
        stats = self._get_statistical_summary(df)
        chart_b64 = await asyncio.to_thread(self._generate_chart, df)

        prompt = f"""You are a data analyst. Analyze this dataset.

Dataset:
- Rows: {stats['shape']['rows']:,}
- Columns: {stats['shape']['columns']}
- Column Names: {', '.join(stats['columns'])}
- Data Types: {json.dumps(stats['dtypes'], indent=2)}
- Missing Values: {json.dumps(stats['null_counts'], indent=2)}
- Stats: {json.dumps(stats.get('numeric_stats', {}), indent=2, default=str)}
- Sample: {json.dumps(stats['sample_data'], indent=2, default=str)}

User Question: {question}

Provide:
## 📊 Dataset Overview
## 🔍 Key Statistical Insights
## ❓ Answer to Question
## 💡 Recommendations
## ⚠️ Data Quality Issues"""

        model = genai.GenerativeModel(self.model_name)
        try:
            response = await model.generate_content_async(prompt)
            ai_insights = response.text
        except Exception as e:
            err_msg = str(e).lower()
            if "429" in err_msg or "exhausted" in err_msg or "quota" in err_msg:
                ai_insights = "🙏 Maaf kijiye, abhi AI service thori busy hai ya limit poori ho gayi hai. Kuch dair baad try karein ya nai API key laga kar check karein."
            else:
                ai_insights = f"⚠️ Oops! API error aagaya: {str(e)[:50]}..."

        return {
            "status": "✅ Analysis complete!",
            "shape": stats['shape'],
            "columns": stats['columns'],
            "null_counts": stats['null_counts'],
            "ai_insights": ai_insights,
            "chart_base64": chart_b64,
            "sample_data": stats['sample_data']
        }
