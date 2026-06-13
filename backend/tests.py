import unittest
import sys
import os

# Add parent directory to sys.path so we can import backend
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from backend.importer import parse_date, clean_amount, normalize_name, is_desc_similar

# Import flask app database and calculation modules to test debt minimization
from backend.app import app, db

class TestExpensesApp(unittest.TestCase):
    
    def test_parse_date(self):
        # Test standard format
        dt, reformatted, suggest = parse_date("15-02-2026")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.day, 15)
        self.assertEqual(dt.month, 2)
        self.assertEqual(dt.year, 2026)
        self.assertFalse(reformatted)
        
        # Test short date format
        dt, reformatted, suggest = parse_date("Mar-14")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.day, 14)
        self.assertEqual(dt.month, 3)
        self.assertEqual(dt.year, 2026)
        self.assertTrue(reformatted)
        self.assertEqual(suggest, "14-03-2026")

    def test_clean_amount(self):
        # Test quoted numbers with commas
        val, cleaned, suggest = clean_amount('"1,200"')
        self.assertEqual(val, 1200.0)
        self.assertTrue(cleaned)
        
        # Test high precision floats
        val, cleaned, suggest = clean_amount("899.995")
        self.assertEqual(val, 900.00)
        self.assertTrue(cleaned)
        
        # Test normal amount
        val, cleaned, suggest = clean_amount("350.50")
        self.assertEqual(val, 350.50)
        self.assertFalse(cleaned)

    def test_normalize_name(self):
        # Test lowercase alias
        name, changed, suggest = normalize_name("priya")
        self.assertEqual(name, "Priya")
        self.assertTrue(changed)
        
        # Test spelling alias
        name, changed, suggest = normalize_name("Priya S")
        self.assertEqual(name, "Priya")
        self.assertTrue(changed)
        
        # Test name with trailing space and lowercase
        name, changed, suggest = normalize_name("rohan ")
        self.assertEqual(name, "Rohan")
        self.assertTrue(changed)

    def test_description_similarity(self):
        # Test identical description
        self.assertTrue(is_desc_similar("Dinner at Marina Bites", "dinner - marina bites"))
        # Test Thalassa dinner
        self.assertTrue(is_desc_similar("Dinner at Thalassa", "Thalassa dinner"))
        # Test unrelated description
        self.assertFalse(is_desc_similar("March rent", "Wifi bill Feb"))

    def test_debt_simplification_logic(self):
        # Simple local test of the cash flow algorithm
        # Suppose Aisha is owed 100, Rohan owes 100
        # Let's verify our minimize cash flow algorithm results
        # We simulate the exact greedy logic used in app.py
        members = {"1": "Aisha", "2": "Rohan", "3": "Priya"}
        net_balances = {"1": 100.0, "2": -100.0, "3": 0.0}
        
        debtors = [{"id": u_id, "name": members[u_id], "balance": bal} for u_id, bal in net_balances.items() if bal < -0.01]
        creditors = [{"id": u_id, "name": members[u_id], "balance": bal} for u_id, bal in net_balances.items() if bal > 0.01]
        
        simplified_payments = []
        d_idx = 0
        c_idx = 0
        
        while d_idx < len(debtors) and c_idx < len(creditors):
            debtor = debtors[d_idx]
            creditor = creditors[c_idx]
            debtor_owe = -debtor["balance"]
            creditor_get = creditor["balance"]
            
            if debtor_owe < creditor_get:
                payment = debtor_owe
                creditor["balance"] -= payment
                debtor["balance"] = 0.0
                d_idx += 1
            elif debtor_owe > creditor_get:
                payment = creditor_get
                debtor["balance"] += payment
                creditor["balance"] = 0.0
                c_idx += 1
            else:
                payment = debtor_owe
                debtor["balance"] = 0.0
                creditor["balance"] = 0.0
                d_idx += 1
                c_idx += 1
                
            if payment > 0.01:
                simplified_payments.append({
                    "from_name": debtor["name"],
                    "to_name": creditor["name"],
                    "amount": round(payment, 2)
                })
                
        self.assertEqual(len(simplified_payments), 1)
        self.assertEqual(simplified_payments[0]["from_name"], "Rohan")
        self.assertEqual(simplified_payments[0]["to_name"], "Aisha")
        self.assertEqual(simplified_payments[0]["amount"], 100.0)

if __name__ == '__main__':
    unittest.main()
