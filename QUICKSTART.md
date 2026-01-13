# 🚀 Quick Start Guide

Get your Finance Reconciliation Automation up and running in 5 minutes!

## ⚡ Installation (2 minutes)

### 1. Install Python
Make sure you have Python 3.8 or higher installed:
```bash
python --version
```

### 2. Install Dependencies
```bash
cd AM-finance-recon
pip install -r requirements.txt
```

### 3. Run the Application
```bash
python app.py
```

Open your browser and navigate to: **http://localhost:5003**

## 📝 First Reconciliation (3 minutes)

### Step 1: Prepare Your File
Create a CSV or Excel file with at least these columns:
- **Transaction Description** (text)
- **Amount** (numbers: negative for expenses, positive for revenue)

Example:
```csv
Description,Amount
Buy Pen from Shopee,-10000
Buy Pencil from Shopee,-5000
Buy Eraser from Shopee,-5000
Stationery Purchase Payment,20000
```

### Step 2: Upload & Process
1. Click **"Choose File"** and select your CSV/Excel file
2. Click **"Upload & Analyze File"**
3. Select your **Amount Column** (e.g., "Amount")
4. Select your **Description Column** (e.g., "Description")
5. Click **"Start Matching Process"**

### Step 3: Review Results
- ✅ View automatically matched transactions
- 🔍 Review items that need manual confirmation
- 📊 Check your reconciliation progress

### Step 4: Export
Choose your export format:
- **New Grouped File** - Organized by match groups
- **Update Original** - Adds status columns to your file
- **Detailed Report** - Comprehensive Excel report

## 💡 Tips for Best Results

### File Preparation
✅ **DO:**
- Use clear, descriptive transaction names
- Keep amount format consistent (negative for expenses)
- Include header row with column names
- Use numeric values for amounts (no currency symbols)

❌ **DON'T:**
- Mix different currencies in one file
- Use text in amount columns
- Leave description field empty
- Use special characters excessively

### Example Good vs Bad Descriptions

**Good:**
- "Invoice to Shopee - Office Supplies Purchase"
- "Payment from Client ABC - Project X"
- "Rent Payment - January 2024"

**Bad:**
- "payment"
- "stuff"
- "123"

## 🎯 Sample Workflow

Use the included `sample_data.csv` to test the system:

```bash
python app.py
```

1. Upload `sample_data.csv`
2. Select "Amount" column
3. Select "Description" column
4. Watch the magic happen! ✨

Expected results:
- ~12 automatic matches
- 85%+ match rate
- Balanced transactions

## 🐛 Troubleshooting

**Problem:** File upload fails
- **Solution:** Check file format (CSV or Excel only), ensure file size < 16MB

**Problem:** No matches found
- **Solution:** Check that descriptions contain meaningful text, not just numbers

**Problem:** Page won't load
- **Solution:** Make sure port 5000 is not in use, try `python app.py` again

**Problem:** "Module not found" error
- **Solution:** Run `pip install -r requirements.txt` again

## 📚 Next Steps

- Read the full [README.md](README.md) for detailed documentation
- Customize matching thresholds in `config.py`
- Explore different export options
- Try with your real financial data

## 🎉 You're Ready!

Your finance reconciliation automation is now set up. Start reconciling transactions and save hours of manual work!

---

**Need Help?** Check the [README.md](README.md) or open an issue on GitHub.