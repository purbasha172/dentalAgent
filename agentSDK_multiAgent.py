from agents import Agent, function_tool, Runner
from typing import Dict, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import uuid
import os
from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables from .env file
load_dotenv()

# Set your OpenAI API key and disable tracing
os.environ["OPENAI_TRACE"] = "false"
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Store patients and appointments in memory
patients = {}  # name -> Patient object
appointments = {}  # name -> list of appointments

@dataclass
class Patient:
    name: str
    phone: str
    email: str
    is_new_patient: bool

@dataclass
class Appointment:
    patient_name: str
    datetime: datetime
    duration: timedelta = timedelta(minutes=30)
    type: str = "regular_checkup"

@function_tool
def register_new_patient(name: str, phone: str, email: str) -> str:
    """Register a new patient with their details"""
    if name in patients:
        return f"Patient {name} is already registered"
    
    patients[name] = Patient(
        name=name,
        phone=phone,
        email=email,
        is_new_patient=True
    )
    return f"New patient {name} registered successfully"

@function_tool
def check_patient_status(name: str) -> str:
    """Check if a patient is new or existing"""
    if name not in patients:
        return "new"
    return "existing"

@function_tool
def get_patient_details(name: str) -> str:
    """Get details of an existing patient"""
    if name not in patients:
        return f"No patient found with name {name}"
    
    patient = patients[name]
    return f"Patient Details:\nName: {patient.name}\nPhone: {patient.phone}\nEmail: {patient.email}\nStatus: {'New' if patient.is_new_patient else 'Existing'} Patient"

@function_tool
def check_slots(date: str) -> str:
    """Check available slots for a given date"""
    try:
        dt = datetime.strptime(date, "%Y-%m-%d")
        slots = ["09:00", "09:30", "10:00", "10:30"]  # Example slots
        return f"Available slots for {date}: {', '.join(slots)}"
    except ValueError:
        return "Invalid date format. Please use YYYY-MM-DD"

@function_tool
def book_appointment(date: str, time: str, name: str, is_new_patient: bool) -> str:
    """Book an appointment for a patient"""
    try:
        dt = datetime.strptime(f"{date} {time}", "%Y-%m-%d %H:%M")
        
        # For new patients, ensure they're registered first
        if is_new_patient and name not in patients:
            return "Please register the patient first using register_new_patient"
        
        if name not in appointments:
            appointments[name] = []
            
        appointments[name].append(Appointment(
            patient_name=name,
            datetime=dt,
            type="initial_consultation" if is_new_patient else "regular_checkup"
        ))
        
        # After first appointment, mark patient as not new
        if name in patients:
            patients[name].is_new_patient = False
            
        return f"{'Initial consultation' if is_new_patient else 'Regular appointment'} booked for {name} on {dt.strftime('%Y-%m-%d at %H:%M')}"
    except ValueError:
        return "Invalid date/time format. Please use YYYY-MM-DD HH:MM"

@function_tool
def cancel_appointment(name: str) -> str:
    """Cancel appointments for a patient"""
    if name in appointments and appointments[name]:
        appointments[name] = []  # Remove all appointments for this patient
        return f"All appointments for {name} have been cancelled"
    return f"No appointments found for {name}"

@function_tool
def get_faq(question: str) -> str:
    """Get answer for frequently asked questions"""
    faqs = {
        "hours": "We are open Monday to Friday, 9 AM to 5 PM",
        "services": "We offer cleanings, fillings, and cosmetic services",
        "insurance": "We accept most major insurance providers"
    }
    print('reached faq')
    return faqs

@function_tool
def check_appointments(name: str) -> str:
    """Check existing appointments for a patient"""
    if name not in appointments or not appointments[name]:
        return f"No appointments found for {name}"
    
    appts = appointments[name]
    result = [f"Appointments for {name}:"]
    for appt in appts:
        result.append(f"- {appt.datetime.strftime('%Y-%m-%d at %H:%M')}")
    return "\n".join(result)

@function_tool
def reschedule_appointment(name: str, old_date: str, old_time: str, new_date: str, new_time: str) -> str:
    """Reschedule an appointment for a patient"""
    try:
        old_dt = datetime.strptime(f"{old_date} {old_time}", "%Y-%m-%d %H:%M")
        new_dt = datetime.strptime(f"{new_date} {new_time}", "%Y-%m-%d %H:%M")
        
        if name not in appointments or not appointments[name]:
            return f"No appointments found for {name}"
        
        # Find the appointment to reschedule
        found = False
        for appt in appointments[name]:
            if appt.datetime == old_dt:
                appt.datetime = new_dt
                found = True
                break
        
        if found:
            return f"Appointment for {name} rescheduled from {old_dt.strftime('%Y-%m-%d at %H:%M')} to {new_dt.strftime('%Y-%m-%d at %H:%M')}"
        else:
            return f"No appointment found for {name} on {old_dt.strftime('%Y-%m-%d at %H:%M')}"
            
    except ValueError:
        return "Invalid date/time format. Please use YYYY-MM-DD HH:MM"

class ConversationState:
    def __init__(self):
        self.current_action = None
        self.patient_name = None
        self.appointment_date = None
        self.appointment_time = None
        self.is_new_patient = False
        
    def reset(self):
        self.__init__()

# Global conversation state
conversation_state = ConversationState()

# Create specialized agents
registration_agent = Agent(
    name="Registration Agent",
    instructions="""You help register new patients. Follow these steps:
    1. Ask for the patient's name if not provided
    2. Use check_patient_status to see if they're new
    3. If new, collect their:
       - Phone number
       - Email address
    4. Use register_new_patient to create their record
    5. Hand off to booking_agent for appointment scheduling
    
    Remember the patient's name and status throughout the conversation.""",
    model="gpt-4o",
    tools=[check_patient_status, register_new_patient, get_patient_details]
)

booking_agent = Agent(
    name="Booking Agent",
    instructions="""You help book appointments and check available slots.
    When booking, follow these steps:
    1. If patient name is not known, ask for it
    2. Use check_patient_status to verify if new or existing
    3. If new, hand off to registration_agent
    4. Use check_slots to show available times
    5. Once date is selected, book the appointment:
       - For new patients: book_appointment(..., is_new_patient=true)
       - For existing patients: book_appointment(..., is_new_patient=false)
    
    Remember the patient's name and appointment details throughout the conversation.""",
    model="gpt-4o",
    tools=[check_slots, book_appointment, check_patient_status]
)

cancellation_agent = Agent(
    name="Cancellation Agent",
    instructions="""You help cancel appointments.
    1. If patient name not provided, ask for it
    2. Use check_appointments to view their appointments
    3. Cancel the specified appointment""",
    model="gpt-4o",
    tools=[check_appointments, cancel_appointment]
)

rescheduling_agent = Agent(
    name="Rescheduling Agent",
    instructions="""You help reschedule appointments. Follow these steps:
    1. If patient name not provided, ask for it
    2. Use check_appointments to see their current appointments
    3. Ask which appointment they want to reschedule
    4. Use check_slots to show available slots for the new date
    5. Use reschedule_appointment to make the change
    
    Remember the patient's name and appointment details throughout the conversation.""",
    model="gpt-4o",
    tools=[check_appointments, check_slots, reschedule_appointment]
)

faq_agent = Agent(
    name="FAQ Agent",
    instructions="You answer questions about our services and policies.",
    model = "gpt-4o",
    tools=[get_faq]
)

# Main dental assistant that routes requests to specialized agents
dental_assistant = Agent(
    name="Dental Assistant",
    instructions="""You are a dental office assistant. Route requests to the appropriate agent:
    - Use registration_agent for new patient registration
    - Use booking_agent for scheduling appointments
    - Use rescheduling_agent for changing existing appointments
    - Use cancellation_agent for cancelling appointments
    - Use faq_agent for general questions
    
    Important:
    1. Maintain conversation context between agent handoffs
    2. Remember patient names and details throughout the conversation
    3. Don't ask for information that was already provided
    4. When booking appointments, ensure new patients are registered first""",
    model="gpt-4o",
    handoffs=[registration_agent, booking_agent, rescheduling_agent, cancellation_agent, faq_agent],
    tools=[check_slots, book_appointment, check_appointments, reschedule_appointment, cancel_appointment, get_faq, check_patient_status, register_new_patient, get_patient_details]
)

async def main():
    global conversation_state
    runner = Runner()
    
    print("Hello! I'm your dental assistant. How can I help you today?")
    
    conversation = []
    while True:
        user_input = input("> ").strip()
        if user_input.lower() in ['quit', 'exit', 'bye']:
            print("Goodbye!")
            break
            
        try:
            # Add user input to conversation
            conversation.append({"role": "user", "content": user_input})
            
            # Join all conversation messages with newlines
            full_context = "\n".join([msg["content"] for msg in conversation])
            
            # Run the main dental assistant with full conversation context
            result = await runner.run(dental_assistant, full_context)
            result_text = str(result)
            print("\nAssistant:", result_text)
            
            # Add assistant's response to conversation
            conversation.append({"role": "assistant", "content": result_text})
            
            # Check if the task is complete
            if any(phrase in result_text.lower() for phrase in [
                "appointment booked", 
                "appointment cancelled",
                "appointment rescheduled",
                "registration complete",
                "no appointments found"
            ]):
                # Keep the last exchange for context but remove older messages
                conversation = conversation[-2:]
            
        except Exception as e:
            print(f"\nError: {str(e)}")
            conversation = []  # Reset conversation on error

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
