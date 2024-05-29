# IMPORTS
from flask import Flask, request, jsonify
from snowflakeConfig import STUDENT_DEFAULT_PASSWORD, init_snowflake_connection  

# Initialize Flask app
app = Flask(__name__)

# Initialize Snowflake connection
def initialize_connection():
    try:
        conn = init_snowflake_connection()  # Get the connection using a function
        if conn is None:
            raise Exception("Failed to create a connection to Snowflake.")
        return conn
    except Exception as e:
        print(f"Error initializing Snowflake connection: {e}")
        return None

conn = initialize_connection()

# Function to fetch student data from Snowflake database
def get_student_data_from_snowflake(student_id):
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM STUDENT WHERE ID = %s", (student_id,))
        specific_student_data = cursor.fetchone()
    except Exception as e:
        raise e
    finally:
        cursor.close()
    return specific_student_data  # specific studentID data

# Function to fetch company data from Snowflake database
def get_company_data_from_snowflake():
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM COMPANY")
        company_data = cursor.fetchall()
    except Exception as e:
        raise e
    finally:
        cursor.close()
    return company_data  # all company data

# Student validation
def validate_student_credentials(student_id, password):
    student_data = get_student_data_from_snowflake(student_id)  # specific studentID data
    if not student_data:
        return {"error": f"Student ID {student_id} doesn't exist"}, 404
    if not password:
        return {"error": f"Password not given"}, 404
    if password!= STUDENT_DEFAULT_PASSWORD:
        return {"error": "Password doesn't match"}, 401 #Unauthorized - Invalid Authentication Creds
    else:
        return student_data, 200 # OK

# Function to get the eligible company of a student by ID
def get_eligible_companies(student_percentage):
    eligible_companies = []
    companies = get_company_data_from_snowflake()
    for company in companies:
        if student_percentage >= float(company[3]): # Required Percentage by the company
            eligible_companies.append(company)
    return eligible_companies

# Function to find the matching skills
def get_matching_skills(student_skills, company_required_skills):
    if not student_skills:
        return []
    student_skills_set = set(skill.strip() for skill in student_skills.split(','))
    company_skills_set = set(skill.strip() for skill in company_required_skills.split(','))
    matching_skills = student_skills_set.intersection(company_skills_set)
    return list(matching_skills), student_skills_set, company_skills_set

# Function to calculate placement likelihood
def calculate_placement_likelihood(student_data, company, weight=0.5, branch_weight=0.2):
    student_percentage = float(student_data[5])
    required_percentage = float(company[3])
    if student_percentage >= required_percentage:
        matching_skills, student_skills, company_required_skills = get_matching_skills(student_data[7], company[5])
        
        # If there are no required skills specified, return 25% as a default
        if not company_required_skills:
            return 25.0   

        # matching skills percentage likelihood
        skills_match_percentage = (len(matching_skills) / len(company_required_skills)) * 100

        # percentage likelihood
        percentage_match = (student_percentage / required_percentage) * 100

        # Adjust likelihood based on branch match
        branch_match = 1 if student_data[6] == company[4] else 0

        # Net - likelihood
        likelihood = ((skills_match_percentage + percentage_match) * weight) + (branch_match * branch_weight)
        return likelihood
    else:
        return 0.0

# Route Function to display Student Details --->     /student/details
@app.route('/student/details', methods=['GET'])
def display_student_details():
    student_id = request.args.get('student_id')
    password = request.args.get('password')

    # if key and values aren't given
    if not student_id or not password:
        return jsonify({"error": "Missing student_id or password"}), 400 # Bad Request - Missing Parameter
    
    student_data, status_code = validate_student_credentials(student_id, password)

    if status_code != 200:
        return jsonify(student_data), status_code
    
    display = {
        "Student ID":          student_data[0],
        "Name":                student_data[1],
        "Branch":              student_data[6],
        "Admission Year":      student_data[2],
        "Placed":              student_data[3],
        "Semester-wise Marks": student_data[4],
        "Percentage":          float(student_data[5]),
        "Certified Skills":    student_data[7]
    }
    return jsonify(display), status_code

@app.route('/student/eligibility', methods=['GET'])
def student_eligibilty():
    student_id = request.args.get('student_id')
    password = request.args.get('password')

    student_data, status_code = validate_student_credentials(student_id, password)

    if status_code != 200:
        return jsonify({"error": "Invalid student ID or password"}), status_code
    
    if student_data[3] == "Yes":
        return jsonify({"message": "You're Already Placed!"}),200
    
    student_percentage = float(student_data[5])
    # get eligible companies based on student's percentage
    eligible_companies = get_eligible_companies(student_percentage)

    if not eligible_companies:
        return jsonify({"message": "No eligible companies found!"}), 404
    
    # print details of company in matched with additional data like likelihood and Matching Skills
    eligible_companies_list = []
    for company in eligible_companies:
        likelihood = calculate_placement_likelihood(student_data= student_data, company= company)
        matching_skills, student_skill_set, _ = get_matching_skills(student_data[7], company[5])
        common_skills = ", ".join(matching_skills) if matching_skills else "No matching skills found!"
        
        company_display = {
            "Branch":                     company[4],
            "Name":                       company[1],
            "Brief Description":          company[2],
            "Required Percentage":        float(company[3]),
            "Required Skills":            company[5],
            "Student Branch":             student_data[6],
            "Student Skills":             list(student_skill_set),
            "Matching Skills":            common_skills,
            "Student Percentage":         student_percentage,
            "Placement Likelihood":       likelihood
        }
        eligible_companies_list.append(company_display)

    return jsonify(eligible_companies_list)

if __name__ == "__main__":
    if conn is None:
        print("Failed to connect to Snowflake. Exiting...")
    else:
        app.run(debug=True)