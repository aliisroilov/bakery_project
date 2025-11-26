# How to Set Initial Salary Balance for Employees

## Overview

The system now provides **three easy ways** to set initial salary balances for your employees. Initial balance represents pre-system debt or salary owed to employees from before the system was implemented.

---

## ✅ Method 1: Command Line (Easiest & Recommended)

Use the new management command to quickly set initial balances:

### Basic Usage

```bash
# Set initial balance for an employee
python manage.py set_initial_balance <username> <amount>

# Examples:
python manage.py set_initial_balance john_driver 500000
python manage.py set_initial_balance ali_nonvoy -200000  # Negative for employee debt
```

### With Rate Configuration (for new employees)

If the employee doesn't have a SalaryRate yet, you can set it at the same time:

```bash
# Driver with weekly rate
python manage.py set_initial_balance john_driver 500000 --rate 150000 --rate-type per_week

# Baker with per-qop rate
python manage.py set_initial_balance ali_nonvoy 300000 --rate 5000 --rate-type per_qop

# Fixed salary employee
python manage.py set_initial_balance manager_bob 1000000 --rate 2000000 --rate-type fixed
```

### List All Employees

View all employees and their current balances:

```bash
python manage.py set_initial_balance --list
```

This will show you:
- Each employee's username and role
- Their salary rate and type
- Current initial balance
- Total earned (auto-calculated + initial balance)
- Total paid
- Current balance due

---

## ✅ Method 2: Django Admin - User Page (Inline Editor)

**NEW FEATURE**: You can now edit salary configuration directly from the User admin page!

### Steps:

1. Go to Django Admin: `/admin/`
2. Click on **"Users"** (not "Salary rates")
3. Click on the employee you want to edit
4. Scroll down to the **"Salary Configuration"** section
5. Enter or modify:
   - **Rate**: The salary rate
   - **Rate type**: Choose from:
     - `Per Qop (meshok)` - For bakers
     - `Per Week` - For drivers
     - `Fixed amount` - For fixed salaries
   - **Initial balance**: The pre-system debt/balance
   - **Notes**: Optional notes
6. Click **"Save"**

### Features:
- ✅ Initial balance now shows in the User list view
- ✅ Inline editor only shows for employees (nonvoy/driver roles)
- ✅ One place to manage user and salary info

---

## ✅ Method 3: Django Admin - Salary Rates Page (Enhanced)

The traditional way, now with improvements:

### Steps:

1. Go to Django Admin: `/admin/`
2. Click on **"Salary rates"**
3. Find the employee or click **"Add salary rate"** to create new
4. Edit the fields:
   - **User**: Select the employee
   - **Rate**: Salary rate amount
   - **Rate type**: Choose type
   - **Initial balance**: Set the initial balance here
   - **Notes**: Optional
5. Click **"Save"**

### Enhanced Features:
- ✅ **Color-coded balances**: Green for positive (owe employee), red for negative (employee owes)
- ✅ **Current balance column**: Shows real-time balance due
- ✅ **Role filtering**: Filter by employee role
- ✅ **Balance summary**: Detailed breakdown when editing showing:
  - Initial balance
  - Auto-calculated earnings
  - Total earned
  - Total paid
  - Current balance due

---

## 📊 How Initial Balance Works

### The Formula:

```
Total Owed = (Auto-calculated Earnings) + Initial Balance - Total Paid
```

### Example:

Let's say you have a driver named "Ali":

1. **Initial Balance**: 500,000 (you owed him from before the system)
2. **Rate**: 150,000 per week
3. **Weeks worked**: 4 weeks
4. **Auto-calculated**: 4 × 150,000 = 600,000

**Total Earned** = 500,000 (initial) + 600,000 (auto) = **1,100,000**

If you've paid him 800,000:
- **Balance Due** = 1,100,000 - 800,000 = **300,000** (you still owe him)

---

## 🎯 Common Scenarios

### Scenario 1: New Employee with Pre-System Debt

```bash
# Employee "Akmal" is owed 750,000 from before the system
python manage.py set_initial_balance akmal 750000 --rate 200000 --rate-type per_week
```

### Scenario 2: Employee Owes You Money

```bash
# Employee "Bobur" owes you 100,000 (advance payment)
python manage.py set_initial_balance bobur -100000
```

### Scenario 3: Updating Existing Balance

```bash
# Change Ali's initial balance from 500,000 to 600,000
python manage.py set_initial_balance ali 600000
```

The command will show you the old and new values.

---

## 🔍 Checking Balances

### Via Command Line:

```bash
python manage.py set_initial_balance --list
```

### Via Admin Panel:

1. Go to `/admin/salary/salaryrate/`
2. View the list with color-coded balances
3. Click on any employee to see detailed breakdown

### Via Employee List (Web Interface):

1. Go to `/salary/` (employee list page)
2. See all employees with their current balance due

---

## ⚠️ Important Notes

1. **Initial balance is separate from auto-calculated earnings**
   - Initial balance: Pre-system debt (manual)
   - Auto-calculated: Based on production/weeks worked (automatic)
   - Total = Initial + Auto-calculated

2. **Negative balances mean employee owes you**
   - Positive: You owe the employee
   - Negative: Employee owes you (advance, debt, etc.)
   - Zero: Settled

3. **Only for employees**
   - Initial balance only applies to `nonvoy` (bakers) and `driver` roles
   - Managers and viewers don't have salary tracking

4. **One SalaryRate per employee**
   - Each user can only have one SalaryRate record
   - Use the update command to change it

---

## 📝 Example Workflow

### Complete Setup for New Employee:

```bash
# 1. Create the user (if not exists)
# Done via admin or createsuperuser

# 2. Set their salary rate and initial balance
python manage.py set_initial_balance ahmad 850000 --rate 180000 --rate-type per_week

# 3. Verify it was set correctly
python manage.py set_initial_balance --list

# 4. Check in admin panel
# Go to /admin/users/user/ and click on Ahmad
# You'll see the Salary Configuration section with all details
```

---

## 🐛 Troubleshooting

### "User does not exist"
- Make sure the username is correct
- Check `/admin/users/user/` to see all usernames

### "SalaryRate already exists" but you can't edit in admin
- Use the command line to update: `python manage.py set_initial_balance <username> <new_amount>`
- Or go to `/admin/salary/salaryrate/` and click on the record

### Initial balance not showing in employee list
- Make sure the employee has a SalaryRate record
- The employee list shows "Balance Due" (total owed), not just initial balance
- Initial balance is included in the calculation

---

## 📚 Files Modified

The following files were created/modified to add this functionality:

1. **`salary/management/commands/set_initial_balance.py`** - New management command
2. **`salary/admin.py`** - Enhanced with color-coding and balance summary
3. **`users/admin.py`** - Added inline SalaryRate editor
4. **`salary/models.py`** - Already had `initial_balance` field (no changes needed)

---

## 🎉 Summary

You now have **three powerful ways** to manage initial salary balances:

1. ⚡ **Command line** - Fast and scriptable
2. 👤 **User admin page** - Edit salary while editing user info
3. 💰 **Salary rates page** - Detailed view with balance breakdown

Choose the method that works best for your workflow!
