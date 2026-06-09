import random
import time
import datetime
import json
import sys

# Configuration dictionary storing normal ranges, abnormal ranges, and thresholds for all vitals.
# This structure allows for easy modification of ranges and thresholds.
VITALS_CONFIG = {
    "SpO2": {
        "normal": (95, 100),
        "abnormal": [(80, 94)],
        "thresholds": {
            "critical_low": 90,
            "alarm_low": 95
        }
    },
    "HR": {
        "normal": (60, 100),
        "abnormal": [(40, 59), (101, 150)],
        "thresholds": {
            "critical_low": 50,
            "alarm_low": 60,
            "alarm_high": 100,
            "critical_high": 120
        }
    },
    "RR": {
        "normal": (12, 20),
        "abnormal": [(8, 11), (21, 40)],
        "thresholds": {
            "alarm_low": 12,
            "alarm_high": 20,
            "critical_high": 30
        }
    },
    "FiO2": {
        "normal": (21, 40),
        "abnormal": [(41, 100)],
        "thresholds": {
            "alarm_high": 40,
            "critical_high": 60
        }
    },
    "PEEP": {
        "normal": (5, 10),
        "abnormal": [(2, 4), (11, 25)],
        "thresholds": {
            "alarm_low": 5,
            "alarm_high": 10,
            "critical_high": 15
        }
    },
    "Tidal Volume": {
        "normal": (400, 600),
        "abnormal": [(200, 399), (601, 800)],
        "thresholds": {
            "critical_low": 300,
            "alarm_low": 400,
            "alarm_high": 600
        }
    }
}

def generate_vital(vital_name):
    """
    Generates a value for a specific vital.
    Returns a normal value with 85-90% probability,
    and introduces an abnormal spike/drop with 10-15% probability.
    """
    config = VITALS_CONFIG[vital_name]
    normal_range = config["normal"]
    abnormal_ranges = config["abnormal"]
    
    # 12% probability of generating an abnormal reading (within 10-15% range)
    if random.random() < 0.12:
        selected_range = random.choice(abnormal_ranges)
        return random.randint(selected_range[0], selected_range[1])
    else:
        return random.randint(normal_range[0], normal_range[1])

def get_status(vital_name, value):
    """
    Determines the status (NORMAL, ALARM, CRITICAL) for a vital reading
    based on the configured thresholds, and returns the status and the violated threshold.
    """
    config = VITALS_CONFIG[vital_name]
    normal_range = config["normal"]
    thresholds = config["thresholds"]
    
    # 1. Check for CRITICAL status first
    if "critical_low" in thresholds and value < thresholds["critical_low"]:
        return "CRITICAL", thresholds["critical_low"]
    if "critical_high" in thresholds and value > thresholds["critical_high"]:
        return "CRITICAL", thresholds["critical_high"]
        
    # 2. Check for ALARM status second
    if "alarm_low" in thresholds and value < thresholds["alarm_low"]:
        return "ALARM", thresholds["alarm_low"]
    if "alarm_high" in thresholds and value > thresholds["alarm_high"]:
        return "ALARM", thresholds["alarm_high"]
        
    # 3. Otherwise, status is NORMAL
    # Return the closest normal boundary as the threshold reference
    if value < normal_range[0]:
        return "NORMAL", normal_range[0]
    elif value > normal_range[1]:
        return "NORMAL", normal_range[1]
    else:
        # If value is inside the normal range, return the boundary that is closer
        if abs(value - normal_range[0]) < abs(value - normal_range[1]):
            return "NORMAL", normal_range[0]
        else:
            return "NORMAL", normal_range[1]

def generate_reading(force_spo2_low=False):
    """
    Randomly selects one of the six vitals, generates a realistic value,
    determines its status and threshold, and formats the output into a dictionary.
    Supports forcing SpO2 to low levels for alert testing.
    """
    if force_spo2_low:
        vital_name = "SpO2"
        # Force a value below 90, e.g. between 80 and 89
        value = random.randint(80, 89)
    else:
        vital_name = random.choice(list(VITALS_CONFIG.keys()))
        value = generate_vital(vital_name)
    
    # Determine status and threshold
    status, threshold = get_status(vital_name, value)
    
    # Get current timestamp in ISO format
    timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    
    return {
        "vital": vital_name,
        "value": value,
        "threshold": threshold,
        "timestamp": timestamp,
        "status": status
    }

def check_alert(reading=None, vital=None, value=None, timestamp=None):
    """
    Reusable alert engine function that checks for server-side threshold breaches.
    Can accept a full reading dictionary, or individual parameters.
    
    Detects breaches for:
      - SpO2 < 90
      - HR > 120 or HR < 50
      - RR > 30
      - FiO2 > 60
      - PEEP > 15
      - Tidal Volume < 300
      
    Returns an alert object (dict) if breached, otherwise None.
    """
    if reading is not None:
        vital = reading.get("vital")
        value = reading.get("value")
        timestamp = reading.get("timestamp")
        
    if vital is None or value is None:
        return None
        
    if timestamp is None:
        timestamp = datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        
    breached = False
    message = ""
    
    if vital == "SpO2" and value < 90:
        breached = True
        message = "Critical oxygen level detected"
    elif vital == "HR":
        if value > 120:
            breached = True
            message = "Critical high heart rate detected"
        elif value < 50:
            breached = True
            message = "Critical low heart rate detected"
    elif vital == "RR" and value > 30:
        breached = True
        message = "Critical high respiratory rate detected"
    elif vital == "FiO2" and value > 60:
        breached = True
        message = "Critical high oxygen concentration detected"
    elif vital == "PEEP" and value > 15:
        breached = True
        message = "Critical high positive end-expiratory pressure detected"
    elif vital == "Tidal Volume" and value < 300:
        breached = True
        message = "Critical low tidal volume detected"
        
    if breached:
        return {
            "type": "alert",
            "vital": vital,
            "value": value,
            "timestamp": timestamp,
            "message": message
        }
    return None

def main():
    """
    Main execution loop. Generates and prints vital readings in JSON format.
    If an alert occurs, checks it and prints the alert JSON to simulate WebSocket integration.
    Supports a test mode that periodically forces SpO2 below 90.
    """
    # Detect test mode from command line arguments
    test_mode = "--test" in sys.argv or "-t" in sys.argv
    
    if test_mode:
        print("[TEST MODE] Active: SpO2 alerts will be forced periodically.")
        
    try:
        iteration = 0
        while True:
            # Force SpO2 low every 3rd iteration in test mode to show alerts
            force_spo2_low = test_mode and (iteration % 3 == 0)
            
            reading = generate_reading(force_spo2_low=force_spo2_low)
            print(json.dumps(reading))
            
            # Run threshold checking and print alert JSON if breached
            alert = check_alert(reading)
            if alert:
                print(json.dumps(alert))
                
            iteration += 1
            time.sleep(2)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()
