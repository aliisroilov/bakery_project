# Quick Fix for Umarxon's Initial Balance

## Problem
Initial balance was set to 480,000 instead of 3,210,000

## Solution Options

### Option 1: Using Command Line (Fastest)

```bash
python manage.py set_initial_balance Umarxon 3210000
```

This will update the initial balance from 480,000 to 3,210,000.

### Option 2: Using Admin Panel

1. Go to: https://sutli-non.uz/admin/users/user/
2. Search for "Umarxon"
3. Click on the user
4. Scroll down to "Salary Configuration"
5. Change "Initial balance" from 480,000 to 3,210,000
6. Click "Save"

### Option 3: Using Salary Rates Page

1. Go to: https://sutli-non.uz/admin/salary/salaryrate/
2. Find Umarxon in the list
3. Click to edit
4. Change "Initial balance" to 3,210,000
5. Click "Save"

## Verify the Change

After fixing, verify by running:

```bash
python manage.py set_initial_balance --list | grep Umarxon
```

Or check in the admin panel.

---

## Important Note About the Command

The command syntax is:

```bash
python manage.py set_initial_balance <username> <initial_balance_amount>
```

**NOT:**

```bash
python manage.py set_initial_balance <username> --rate <amount>  # WRONG!
```

The `--rate` parameter is for the salary rate, not the initial balance.

**Examples:**

```bash
# Correct - Sets INITIAL BALANCE to 3,210,000
python manage.py set_initial_balance Umarxon 3210000

# Correct - Sets INITIAL BALANCE to 3,210,000 AND rate to 200,000/week
python manage.py set_initial_balance Umarxon 3210000 --rate 200000 --rate-type per_week

# WRONG - Sets initial balance to 0 and rate to 3,210,000
python manage.py set_initial_balance Umarxon --rate 3210000
```
