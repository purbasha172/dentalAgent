import os
import openai
from datetime import datetime, timedelta
import re
from dotenv import load_dotenv
import json

# Load environment variables
load_dotenv()

# Set OpenAI API key
openai.api_key = os.getenv('OPENAI_API_KEY')

class DentalAssistant:
    def __init__(self):
        self.patients = {}  # Dictionary to store patient information
        self.appointments = {}  # Dictionary to store appointments
        self.current_patient = None
        self.conversation_history = []
        self.practice_info = {
            "name": "Smile Bright Dental",
            "hours": "Monday-Friday: 9:00 AM - 6:00 PM",
            "services": {
                "Cleaning": {"duration": "60", "cost": "100"},
                "Check-up": {"duration": "30", "cost": "75"},
                "Fillings": {"duration": "60", "cost": "150"},
                "Root Canal": {"duration": "90", "cost": "800"},
                "Crown": {"duration": "90", "cost": "1000"},
                "Extraction": {"duration": "45", "cost": "200"}
            },
            "location": "123 Dental Street, Suite 100",
            "phone": "(555) 123-4567",
            "faqs": {
                "parking": "Yes, we have free parking available in front of the clinic.",
                "insurance": "We accept most major insurance providers. Please contact us with your specific provider.",
                "emergency": "Yes, we provide emergency dental services. Call our emergency line at (555) 999-9999.",
                "payment": "We accept cash, credit cards, and offer various payment plans.",
                "cancellation": "Please provide at least 24 hours notice for cancellations to avoid any fees."
            }
        }

    def get_system_prompt(self):
        """Generate the system prompt for OpenAI."""
        return f"""You are a friendly and professional dental front desk assistant at {self.practice_info['name']}.
Your role is to help patients schedule appointments, answer questions about our services, and manage bookings.

Practice Information:
- Hours: {self.practice_info['hours']}
- Location: {self.practice_info['location']}
- Phone: {self.practice_info['phone']}

Available Services:
{json.dumps(self.practice_info['services'], indent=2)}

When scheduling appointments:
1. Verify if they are a new or existing patient
2. Collect necessary information (name, phone, email, DOB for new patients)
3. Help them choose a service
4. Find a suitable appointment time
5. Confirm the booking

For appointment-related requests, respond with ONLY the appropriate action tag:
- For booking: "ACTION: BOOK_APPOINTMENT"
- For rescheduling: "ACTION: RESCHEDULE_APPOINTMENT"
- For cancelling: "ACTION: CANCEL_APPOINTMENT"
- For viewing history: "ACTION: VIEW_APPOINTMENTS"

For general inquiries about services, policies, or other topics, provide a helpful response without an action tag.
Keep responses concise and professional. If you need specific information, ask for it clearly.
Always validate dates and times against business hours before confirming appointments."""

    def generate_response(self, user_input):
        """Generate a response using OpenAI's API."""
        # Check for direct commands first
        user_input_lower = user_input.lower()
        
        # Direct command handling
        if any(phrase in user_input_lower for phrase in [
            "show my appointment", "view my appointment", "appointment history",
            "my appointments", "check my appointments"
        ]):
            self.handle_appointment_history()
            return "I've displayed your appointment history above."
            
        if "book" in user_input_lower and "appointment" in user_input_lower:
            self.handle_booking()
            return "I've helped you book your appointment above."
            
        if "cancel" in user_input_lower and "appointment" in user_input_lower:
            self.handle_cancellation()
            return "I've helped you with your cancellation request above."
            
        if "reschedule" in user_input_lower and "appointment" in user_input_lower:
            self.handle_rescheduling()
            return "I've helped you reschedule your appointment above."

        # Add user input to conversation history
        self.conversation_history.append({"role": "user", "content": user_input})
        
        try:
            # Get completion from OpenAI
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    *self.conversation_history
                ],
                temperature=0.7,
                max_tokens=150
            )
            
            # Extract and store assistant's response
            assistant_response = response.choices[0].message['content']
            self.conversation_history.append({"role": "assistant", "content": assistant_response})
            
            # Process any actions in the response
            action_result = self.process_assistant_response(assistant_response)
            if action_result:
                return action_result
            
            return assistant_response
            
        except Exception as e:
            return f"I apologize, but I encountered an error: {str(e)}"

    def process_assistant_response(self, response):
        """Process any actions needed based on the assistant's response."""
        # Check for appointment-related intents
        if "ACTION: BOOK_APPOINTMENT" in response:
            return self.handle_booking()
        elif "ACTION: RESCHEDULE_APPOINTMENT" in response:
            return self.handle_rescheduling()
        elif "ACTION: CANCEL_APPOINTMENT" in response:
            return self.handle_cancellation()
        elif "ACTION: VIEW_APPOINTMENTS" in response:
            return self.handle_appointment_history()
        return None

    def handle_booking(self):
        """Handle the appointment booking process."""
        # Check if patient exists
        phone = input("\nPlease enter your phone number (10 digits): ").strip()
        patient_id = self.find_patient(phone)
        
        if not patient_id:
            print("\nLooks like you're a new patient. Let's get you registered.")
            name = input("Full Name: ").strip()
            email = input("Email Address: ").strip()
            dob = input("Date of Birth (DD/MM/YYYY): ").strip()
            patient_id = self.register_patient(name, phone, email, dob)
            print("\nRegistration successful!")
        else:
            print(f"\nWelcome back, {self.patients[patient_id]['name']}!")
        
        # Show available services with duration and cost
        print("\nAvailable Services:")
        for i, (service, details) in enumerate(self.practice_info["services"].items(), 1):
            print(f"{i}. {service} ({details['duration']} mins, ${details['cost']})")

        # Get service selection
        while True:
            try:
                service_num = int(input("\nSelect service number: "))
                if 1 <= service_num <= len(self.practice_info["services"]):
                    service = list(self.practice_info["services"].keys())[service_num - 1]
                    break
                print("Invalid selection. Please try again.")
            except ValueError:
                print("Please enter a valid number.")

        # Get appointment date and time
        print("\nAppointment Scheduling")
        print("Available hours: Monday-Friday, 9:00 AM - 6:00 PM")
        
        while True:
            date_str = input("Preferred date (DD/MM/YYYY): ").strip()
            time_str = input("Preferred time (HH:MM, 24-hour format): ").strip()
            
            is_valid, error_msg = self.validate_appointment_time(date_str, time_str)
            if is_valid:
                appointment_id, error = self.book_appointment(patient_id, date_str, time_str, service)
                if appointment_id:
                    print(f"\nAppointment successfully booked!")
                    print(f"Service: {service}")
                    print(f"Duration: {self.practice_info['services'][service]['duration']} minutes")
                    print(f"Cost: ${self.practice_info['services'][service]['cost']}")
                    print(f"Date: {date_str}")
                    print(f"Time: {time_str}")
                    print(f"Appointment ID: {appointment_id}")
                    return
                print(f"Booking failed: {error}")
            else:
                print(f"Invalid date/time: {error_msg}")
            
            if input("\nWould you like to try another date/time? (yes/no): ").strip().lower() != 'yes':
                return

    def handle_rescheduling(self):
        """Handle the appointment rescheduling process."""
        # Verify patient
        phone = input("\nPlease enter your phone number (10 digits): ").strip()
        patient_id = self.find_patient(phone)
        
        if not patient_id:
            print("No appointments found. Please register as a new patient first.")
            return
        
        # Get active appointments
        appointments = [app for app in self.get_patient_appointments(patient_id) 
                       if app["status"] == "scheduled"]
        
        if not appointments:
            print("You don't have any active appointments to reschedule.")
            return
        
        # Show appointments
        print("\nYour appointments:")
        for app in appointments:
            print(f"ID: {app['id']} | {app['service']} on {app['date']} at {app['time']}")
        
        # Get appointment selection
        while True:
            try:
                app_id = int(input("\nEnter appointment ID to reschedule: "))
                if any(app['id'] == app_id for app in appointments):
                    break
                print("Invalid appointment ID. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Get new date and time
        print("\nNew Appointment Time")
        print("Available hours: Monday-Friday, 9:00 AM - 6:00 PM")
        
        while True:
            date_str = input("New date (DD/MM/YYYY): ").strip()
            time_str = input("New time (HH:MM, 24-hour format): ").strip()
            
            success, message = self.reschedule_appointment(app_id, date_str, time_str)
            if success:
                print("\nAppointment successfully rescheduled!")
                print(f"New date: {date_str}")
                print(f"New time: {time_str}")
                return
            
            print(f"Rescheduling failed: {message}")
            if input("\nWould you like to try another date/time? (yes/no): ").strip().lower() != 'yes':
                return

    def handle_cancellation(self):
        """Handle the appointment cancellation process."""
        # Verify patient
        phone = input("\nPlease enter your phone number (10 digits): ").strip()
        patient_id = self.find_patient(phone)
        
        if not patient_id:
            print("No appointments found. Please register as a new patient first.")
            return
        
        # Get active appointments
        appointments = [app for app in self.get_patient_appointments(patient_id) 
                       if app["status"] == "scheduled"]
        
        if not appointments:
            print("You don't have any active appointments to cancel.")
            return
        
        # Show appointments
        print("\nYour appointments:")
        for app in appointments:
            print(f"ID: {app['id']} | {app['service']} on {app['date']} at {app['time']}")
        
        # Get appointment selection
        while True:
            try:
                app_id = int(input("\nEnter appointment ID to cancel: "))
                if any(app['id'] == app_id for app in appointments):
                    break
                print("Invalid appointment ID. Please try again.")
            except ValueError:
                print("Please enter a valid number.")
        
        # Confirm cancellation
        if input("\nAre you sure you want to cancel this appointment? (yes/no): ").strip().lower() == 'yes':
            success, message = self.cancel_appointment(app_id)
            if success:
                print("\nAppointment successfully cancelled!")
            else:
                print(f"Cancellation failed: {message}")

    def handle_appointment_history(self):
        """Handle viewing appointment history."""
        # Verify patient
        phone = input("\nPlease enter your phone number (10 digits): ").strip()
        patient_id = self.find_patient(phone)
        
        if not patient_id:
            print("No appointments found. Please register as a new patient first.")
            return
        
        # Get all appointments including cancelled ones
        appointments = self.get_patient_appointments(patient_id, include_cancelled=True)
        
        if not appointments:
            print("No appointment history found.")
            return
        
        # Sort appointments by date and time
        appointments.sort(key=lambda x: (
            datetime.strptime(x['date'], '%d/%m/%Y'),
            datetime.strptime(x['time'], '%H:%M')
        ))
        
        # Group appointments by status
        scheduled = [app for app in appointments if app['status'] == 'scheduled']
        cancelled = [app for app in appointments if app['status'] == 'cancelled']
        
        # Display patient information
        patient = self.patients[patient_id]
        print(f"\nAppointment History for {patient['name']}")
        print(f"Phone: {patient['phone']}")
        print(f"Email: {patient['email']}")
        print("=" * 50)
        
        # Display scheduled appointments
        if scheduled:
            print("\nUpcoming Appointments:")
            for app in scheduled:
                service_details = self.practice_info['services'][app['service']]
                print(f"\nID: {app['id']}")
                print(f"Service: {app['service']}")
                print(f"Date: {app['date']}")
                print(f"Time: {app['time']}")
                print(f"Duration: {service_details['duration']} minutes")
                print(f"Cost: ${service_details['cost']}")
        
        # Display cancelled appointments
        if cancelled:
            print("\nCancelled Appointments:")
            for app in cancelled:
                print(f"\nID: {app['id']}")
                print(f"Service: {app['service']}")
                print(f"Date: {app['date']}")
                print(f"Time: {app['time']}")
                print(f"Status: Cancelled")
        
        # Show options for appointment management
        if scheduled:
            print("\nOptions:")
            print("1. Reschedule an appointment")
            print("2. Cancel an appointment")
            print("3. Return to main menu")
            
            choice = input("\nSelect an option (1-3): ").strip()
            if choice == '1':
                return self.handle_rescheduling()
            elif choice == '2':
                return self.handle_cancellation()

    def get_patient_appointments(self, patient_id, include_cancelled=False):
        """Get all appointments for a patient."""
        if patient_id in self.patients:
            appointments = [self.appointments[app_id] for app_id in self.patients[patient_id]["appointments"]]
            if not include_cancelled:
                appointments = [app for app in appointments if app["status"] == "scheduled"]
            return appointments
        return []

    def validate_appointment_time(self, date_str, time_str=None):
        """Validate the appointment date and time."""
        try:
            date = datetime.strptime(date_str, "%d/%m/%Y").date()
            current_date = datetime.now().date()
            
            if date < current_date:
                return False, "Cannot book appointments in the past."
            
            if date > current_date + timedelta(days=90):
                return False, "Appointments can only be booked up to 90 days in advance."
            
            if date.weekday() >= 5:
                return False, "Appointments are only available Monday through Friday."
            
            if time_str:
                time = datetime.strptime(time_str, "%H:%M").time()
                if time.hour < 9 or time.hour >= 18:
                    return False, "Appointments are only available between 9:00 AM and 6:00 PM."
            
            return True, None
            
        except ValueError:
            return False, "Invalid date/time format."

    def register_patient(self, name, phone, email, dob):
        """Register a new patient."""
        patient_id = len(self.patients) + 1
        self.patients[patient_id] = {
            "name": name,
            "phone": phone,
            "email": email,
            "dob": dob,
            "appointments": []
        }
        return patient_id

    def find_patient(self, phone):
        """Find a patient by phone number."""
        for patient_id, patient in self.patients.items():
            if patient["phone"] == phone:
                return patient_id
        return None

    def book_appointment(self, patient_id, date, time, service):
        """Book an appointment for a patient."""
        is_valid, error_msg = self.validate_appointment_time(date, time)
        if not is_valid:
            return None, error_msg

        appointment_id = len(self.appointments) + 1
        appointment = {
            "id": appointment_id,
            "patient_id": patient_id,
            "date": date,
            "time": time,
            "service": service,
            "status": "scheduled"
        }
        
        self.appointments[appointment_id] = appointment
        self.patients[patient_id]["appointments"].append(appointment_id)
        return appointment_id, None

    def cancel_appointment(self, appointment_id):
        """Cancel an appointment."""
        if appointment_id in self.appointments:
            self.appointments[appointment_id]["status"] = "cancelled"
            return True, "Appointment cancelled successfully."
        return False, "Appointment not found."

    def reschedule_appointment(self, appointment_id, new_date, new_time):
        """Reschedule an appointment."""
        if appointment_id not in self.appointments:
            return False, "Appointment not found."
            
        appointment = self.appointments[appointment_id]
        if appointment["status"] == "cancelled":
            return False, "Cannot reschedule a cancelled appointment."
            
        is_valid, error_msg = self.validate_appointment_time(new_date, new_time)
        if not is_valid:
            return False, error_msg
            
        appointment["date"] = new_date
        appointment["time"] = new_time
        return True, f"Appointment successfully rescheduled to {new_date} at {new_time}."

def main():
    print("Welcome to Smile Bright Dental!")
    print("How can I help you today? (Type 'quit' to exit)")
    print("\nYou can:")
    print("- Book an appointment")
    print("- Cancel or reschedule existing appointments")
    print("- Ask questions about our services and policies")
    
    assistant = DentalAssistant()
    
    while True:
        user_input = input("\nYou: ").strip()
        
        if user_input.lower() == 'quit':
            print("Thank you for using our service. Have a great day!")
            break
            
        response = assistant.generate_response(user_input)
        print(f"\nAssistant: {response}")

if __name__ == "__main__":
    main()