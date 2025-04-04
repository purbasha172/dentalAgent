import os
from openai import OpenAI
from datetime import datetime, timedelta
import re
from dotenv import load_dotenv
import json


# Load environment variables
load_dotenv()

# Set OpenAI API key
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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

IMPORTANT: For ALL appointment-related actions (booking, cancellation, rescheduling, viewing history):
1. ALWAYS ask for the patient's name FIRST before proceeding with any action
2. Only proceed with the requested action after confirming patient identity
3. If a request is made without providing a name, politely ask for it

When handling new appointments:
1. After getting patient name, ask if they are a new or existing patient
2. For new patients: Ask for contact information and preferred appointment time
3. For existing patients: Look up their information
4. Help them choose a service from our available options
5. Suggest available time slots within our business hours
6. Provide clear confirmation of the booking details

For appointment history:
1. Always ask for the patient's name first before showing any history
2. Present appointment history in a clear, chronological format
3. Include important details like service type, date, time, and status
4. If no appointments are found, provide a polite response indicating this

For cancellations:
1. First ask for the patient's name if not provided
2. Look up and confirm their existing appointment details
3. Inform about our cancellation policy
4. Process the cancellation only after confirmation

For rescheduling:
1. First ask for the patient's name if not provided
2. Look up and confirm their existing appointment
3. Ask for preferred new date and time
4. Help find a suitable time within business hours
5. Provide clear confirmation of the changes

Always maintain a professional and helpful tone. If you need specific information, ask for it clearly.
Validate that requested appointments fall within business hours.
Provide clear, direct responses to questions about our services, policies, or other inquiries."""

    def get_available_functions(self):
        """Return the list of available functions for OpenAI"""
        return [
            {
                "type": "function",
                "name": "book_appointment",
                "description": "Book a new dental appointment",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Patient's full name"
                        },
                        "phone": {
                            "type": "string",
                            "description": "Patient's phone number"
                        },
                        "email": {
                            "type": "string",
                            "description": "Patient's email address"
                        },
                        "service": {
                            "type": "string",
                            "enum": list(self.practice_info["services"].keys()),
                            "description": "Type of dental service required"
                        },
                        "date": {
                            "type": "string",
                            "description": "Appointment date in YYYY-MM-DD format"
                        },
                        "time": {
                            "type": "string",
                            "description": "Appointment time in HH:MM format"
                        }
                    },
                    "required": ["name", "phone", "service", "date", "time"]
                }
            },
            {
                "type": "function",
                "name": "get_appointment_history",
                "description": "Get appointment history for a patient",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Patient's full name"
                        }
                    },
                    "required": ["name"]
                }
            },
            {
                "type": "function",
                "name": "cancel_appointment",
                "description": "Cancel an existing appointment",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "appointment_id": {
                            "type": "string",
                            "description": "Unique identifier for the appointment to cancel"
                        }
                    },
                    "required": ["appointment_id"]
                }
            },
            {
                "type": "function",
                "name": "reschedule_appointment",
                "description": "Reschedule an existing appointment",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "appointment_id": {
                            "type": "string",
                            "description": "Unique identifier for the appointment to reschedule"
                        },
                        "new_date": {
                            "type": "string",
                            "description": "New appointment date in YYYY-MM-DD format"
                        },
                        "new_time": {
                            "type": "string",
                            "description": "New appointment time in HH:MM format"
                        },
                        "patient_name": {
                            "type": "string",
                            "description": "Patient's full name (alternative to appointment_id)"
                        }
                    },
                    "required": ["new_date", "new_time"]
                }
            }
        ]

    def get_appointment_history(self, name=None):
        """
        Get appointment history for a patient

        Args:
            name (str, optional): Patient's full name. If not provided, return empty list.

        Returns:
            list: List of appointments for the patient
        """
        if not name:
            return []

        patient_appointments = []
        for appointment_id, appointment in self.appointments.items():
            if appointment["patient"]["name"].lower() == name.lower():
                appointment_info = {
                    "id": appointment_id,
                    "service": appointment["service"],
                    "date": appointment["date"],
                    "time": appointment["time"],
                    "status": appointment["status"]
                }
                patient_appointments.append(appointment_info)
        
        return patient_appointments



    def generate_response(self, user_input):
        """Generate a response using OpenAI's GPT-4 API."""
        try:
            # Add user's message to conversation history
            self.conversation_history.append({"role": "user", "content": user_input})
            
            # Get available functions
            functions = self.get_available_functions()
            
            # Make the API call
            response = client.responses.create(
                model="gpt-4o",
                input="\n".join(str(msg["content"]) for msg in [{"role": "system", "content": self.get_system_prompt()}, *self.conversation_history]),
                tools=functions,
                tool_choice="auto"
            )
            
            # Get the response
            assistant_message = response.output[0]
            
            # Check if the model wants to call a function
            if assistant_message.type == "function_call":
                function_name = assistant_message.name
                function_args = json.loads(assistant_message.arguments)
                
                # Execute the function
                if function_name == "book_appointment":
                    patient_info = {
                        "name": function_args["name"],
                        "phone": function_args["phone"],
                        "email": function_args.get("email", "")
                    }
                    result = self.book_appointment(
                        patient_info,
                        function_args["service"],
                        function_args["date"],
                        function_args["time"]
                    )
                    function_response = "Appointment booked successfully." if result else "Failed to book appointment. Time slot might be unavailable."
                
                elif function_name == "get_appointment_history":
                    result = self.get_appointment_history(function_args["name"])
                    if result:
                        appointments_str = "\n".join([
                            f"- {appt['date']} at {appt['time']}: {appt['service']} ({appt['status']})"
                            for appt in result
                        ])
                        function_response = f"Here are your appointments:\n{appointments_str}"
                    else:
                        function_response = f"No appointments found for patient '{function_args['name']}'."
                
                elif function_name == "cancel_appointment":
                    result = self.cancel_appointment(function_args["appointment_id"])
                    function_response = "Appointment cancelled successfully." if result else "Failed to cancel appointment. Appointment ID not found."
                
                elif function_name == "reschedule_appointment":
                    result = self.reschedule_appointment(
                        function_args.get("appointment_id"),
                        function_args.get("new_date"),
                        function_args.get("new_time"),
                        function_args.get("patient_name")
                    )
                    function_response = "Appointment rescheduled successfully." if result else "Failed to reschedule appointment. Time slot might be unavailable or appointment ID not found."
                
                # Add function response to conversation history
                self.conversation_history.append({
                    "role": "assistant",
                    "content": function_response
                })
                
                # Get final response from GPT
                second_response = client.responses.create(
                    model="gpt-4o",
                    input="\n".join(str(msg["content"]) for msg in [{"role": "system", "content": self.get_system_prompt()}, *self.conversation_history]),
                    temperature=0.7  # Add some variability to responses
                )
                
                response_text = second_response.output_text
            else:
                response_text = assistant_message.content[0].text
            
            # Add assistant's response to conversation history
            self.conversation_history.append({
                "role": "assistant",
                "content": response_text
            })
            
            return response_text
            
        except Exception as e:
            print(f"Error generating response: {str(e)}")
            return "I apologize, but I encountered an error. Please try again or contact support."

    def book_appointment(self, patient_info, service, date, time):
        """
        Book a new appointment for a patient
        
        Args:
            patient_info (dict): Patient details including name, phone, email
            service (str): Type of dental service
            date (str): Appointment date (YYYY-MM-DD)
            time (str): Appointment time (HH:MM)
            
        Returns:
            dict: Appointment details if successful, None if failed
        """
        # Validate service exists
        if service not in self.practice_info["services"]:
            return None
            
        # Create unique appointment ID
        appointment_id = f"{date}-{time}-{patient_info['name']}"
        
        # Check if timeslot is available
        if appointment_id in self.appointments:
            return None
            
        # Create appointment
        appointment = {
            "patient": patient_info,
            "service": service,
            "date": date,
            "time": time,
            "duration": self.practice_info["services"][service]["duration"],
            "status": "confirmed"
        }
        
        # Store appointment
        self.appointments[appointment_id] = appointment
        return appointment

    def cancel_appointment(self, appointment_id):
        """
        Cancel an existing appointment
        
        Args:
            appointment_id (str): Unique appointment identifier
            
        Returns:
            bool: True if cancelled successfully, False otherwise
        """
        if appointment_id not in self.appointments:
            return False
            
        self.appointments[appointment_id]["status"] = "cancelled"
        return True

    def reschedule_appointment(self, appointment_id=None, new_date=None, new_time=None, patient_name=None):
        """
        Reschedule an existing appointment
        
        Args:
            appointment_id (str, optional): Unique appointment identifier
            new_date (str, optional): New appointment date (YYYY-MM-DD)
            new_time (str, optional): New appointment time (HH:MM)
            patient_name (str, optional): Patient's name to look up appointment
            
        Returns:
            dict: Updated appointment details if successful, None if failed
        """
        # If no appointment_id but patient name is provided, look up their active appointment
        if not appointment_id and patient_name:
            active_appointments = self.find_appointment_by_name(patient_name)
            if not active_appointments:
                return None
            # If patient has only one active appointment, use that
            if len(active_appointments) == 1:
                appointment_id = list(active_appointments.keys())[0]
            else:
                # Multiple appointments found - this should be handled by the conversation flow
                return None

        # Proceed with rescheduling if we have an appointment_id
        if not appointment_id or appointment_id not in self.appointments:
            return None
            
        if not new_date or not new_time:
            return None
            
        # Get the existing appointment
        appointment = self.appointments[appointment_id]
        
        # Create new appointment ID
        new_appointment_id = f"{new_date}-{new_time}-{appointment['patient']['name']}"
        
        # Check if new timeslot is available
        if new_appointment_id in self.appointments and new_appointment_id != appointment_id:
            return None
            
        # Update appointment
        appointment["date"] = new_date
        appointment["time"] = new_time
        
        # If the appointment ID changed, update the dictionary
        if new_appointment_id != appointment_id:
            self.appointments[new_appointment_id] = appointment
            del self.appointments[appointment_id]
        
        return appointment

def main():
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