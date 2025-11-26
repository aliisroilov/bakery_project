# Fix Options for Umarxon's Balance

## First: Diagnose the Issue

Run this command to see what's wrong:

```bash
python manage.py check_balance Umarxon
```

This will show you exactly:
- What the initial balance is set to
- What the rate is
- All payment records
- Why the balance is 480,000 instead of 3,210,000

---

## Common Fixes

### Fix 1: Delete Incorrect Payment Records

If there are payment records that shouldn't exist:

**Option A: Via Admin Panel**
1. Go to: https://sutli-non.uz/admin/salary/salarypayment/
2. Filter by user = "Umarxon"
3. Delete the incorrect payment(s)

**Option B: Via Command Line** (delete ALL payments for Umarxon)
```bash
python manage.py shell -c "
from salary.models import SalaryPayment
from users.models import User

user = User.objects.get(username='Umarxon')
payments = SalaryPayment.objects.filter(user=user)
print(f'Found {payments.count()} payments, total: {sum(p.amount for p in payments):,}')
# Uncomment next line to delete:
# payments.delete()
"
```

---

### Fix 2: Correct the Salary Rate

If the rate is set incorrectly (should be weekly rate, not initial balance):

```bash
python manage.py shell -c "
from users.models import User
user = User.objects.get(username='Umarxon')
sr = user.salary_rate
print(f'Current rate: {sr.rate}')
print(f'Current initial_balance: {sr.initial_balance}')

# If rate is wrong, set it correctly:
# sr.rate = 150000  # or whatever the correct weekly rate is
# sr.save()
"
```

---

### Fix 3: Set Both Initial Balance and Rate Correctly

If Umarxon should have:
- Initial balance: 3,210,000
- Weekly rate: 150,000 (example)

```bash
python manage.py shell -c "
from users.models import User
user = User.objects.get(username='Umarxon')
sr = user.salary_rate
sr.initial_balance = 3210000
sr.rate = 150000  # Set correct weekly rate
sr.rate_type = 'per_week'
sr.save()
print('Updated!')
"
```

---

### Fix 4: Start Fresh

If everything is messed up, delete the SalaryRate and payments, then recreate:

```bash
# 1. Delete everything
python manage.py shell -c "
from users.models import User
user = User.objects.get(username='Umarxon')
user.salary_payments.all().delete()
user.salary_rate.delete()
print('Deleted all salary data for Umarxon')
"

# 2. Recreate with correct values
python manage.py set_initial_balance Umarxon 3210000 --rate 150000 --rate-type per_week
```

---

## After Fixing

Verify the fix worked:

```bash
# Check balance
python manage.py check_balance Umarxon

# Or list all employees
python manage.py set_initial_balance --list | grep Umarxon
```

---

## Understanding the Balance Calculation

The system calculates like this:

```
Total Earned = Initial Balance + Auto-calculated Earnings
Balance Due = Total Earned - Total Paid
```

**Example 1: Just initial balance, no work yet**
- Initial Balance: 3,210,000
- Auto-calculated: 0 (no work tracked)
- Total Earned: 3,210,000
- Total Paid: 0
- **Balance Due: 3,210,000** ✓

**Example 2: Initial balance + 2 weeks of work**
- Initial Balance: 3,210,000
- Weekly Rate: 150,000
- Weeks worked: 2
- Auto-calculated: 300,000
- Total Earned: 3,510,000
- Total Paid: 0
- **Balance Due: 3,510,000**

**Example 3: Initial balance + payment made**
- Initial Balance: 3,210,000
- Auto-calculated: 0
- Total Earned: 3,210,000
- Total Paid: 2,730,000 ⚠️ (wrong payment)
- **Balance Due: 480,000** ⚠️ (This is your issue!)

---

## Next Steps

1. Run: `python manage.py check_balance Umarxon`
2. Look at the output
3. Choose the appropriate fix above
4. Verify it worked
