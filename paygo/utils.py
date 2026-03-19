

def get_payment_plan_details(plan):
    plans = {
        "Plan_1": {
            "deposit": 4500,
            "weekly_payment": 190,
            "weeks": 40,
            "total_price": 12100,
        },
        "Plan_2": {
            "deposit": 2500,
            "weekly_payment": 250,
            "weeks": 48,
            "total_price": 14500,
        },
    }
    return plans.get(plan)