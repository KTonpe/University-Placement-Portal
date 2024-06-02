# IMPORTS
from flask import Flask, request, jsonify
import html
import re
from snowflakeConfig import STUDENT_DEFAULT_PASSWORD, init_snowflake_connection, COMPANY_PASSWORD

#--------------------------------------------------------------------------------------------------------------------------------------------------

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

def get_specific_company_data_from_snowflake(company_id):
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM COMPANY WHERE ID = %s", (company_id,))
        specific_company_data = cursor.fetchone()
    except Exception as e:
        raise e
    finally:
        cursor.close()
    return specific_company_data  # specific companyID data

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

# Function to validate company
def validate_company_credentials(company_id,company_password):
    specific_company_data = get_specific_company_data_from_snowflake(company_id)  # specific companyID data
    if not specific_company_data:
        return {"error": f"Company ID {company_id} doesn't exist"}, 404
    if not company_password:
        return {"error": f"Password not given"}, 404
    if company_password!= COMPANY_PASSWORD:
        return {"error": "Password doesn't match"}, 401 #Unauthorized - Invalid Authentication Creds
    else:
        return specific_company_data, 200 # OK

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

# Function to calculate the persenatge    
def calculate_percentage(semester_wise_marks):
    try:
        # Split the string to extract individual marks
        marks_list = semester_wise_marks.split(',')
        
        # Convert the string marks to integers
        marks_list = list(map(int, marks_list))
        
        # Check if there are any marks provided
        if len(marks_list) == 0:
            raise ValueError("No marks provided")
        
        # Calculate the sum of the marks
        total_marks = sum(marks_list)
        
        # Calculate the number of subjects
        num_subjects = len(marks_list)
        
        # Calculate the average of the marks
        average_marks = total_marks / num_subjects
        
        # Calculate the percentage
        percentage = average_marks  # Since full marks for each subject is 100
        
        return percentage
    
    except ValueError as e:
        # Handle specific error related to invalid integer conversion or no marks provided
        raise ValueError(f"Invalid marks format: {e}")
    except ZeroDivisionError:
        # Handle the case where division by zero might occur
        raise ZeroDivisionError("Number of subjects is zero, cannot calculate percentage")

#Function to Validate the given data
def validate_data_types_for_student_Add(data):
    if not isinstance(data.get('student_id'), str):
        return "student_id should be a string"
    if not isinstance(data.get('name'), str):
        return "name should be a string"
    if not isinstance(data.get('branch'), str):
        return "branch should be a string"
    if not isinstance(data.get('admission_year'), str):
        return "admission_year should be a string"
    if not isinstance(data.get('placed', 'No'), str):
        return "placed should be a string"
    if not isinstance(data.get('semester_wise_marks'), str):
        return "semester_wise_marks should be a string"
    if not isinstance(data.get('certified_skills', ''), str):
        return "certified_skills should be a string"
    
    # Validate branch
    valid_branches = ["CS", "CIVIL", "ELECTRONIC", "MECH", "IT"]
    if data.get('branch') not in valid_branches:
        return f"branch should be one of {valid_branches}"
    
    # Validate marks format
    marks = data.get('semester_wise_marks')
    try:
        marks_list = marks.split(',')
        for mark in marks_list:
            int(mark)  # This will raise ValueError if conversion fails
    except ValueError:
        return "semester_wise_marks should contain valid integers separated by commas"

    
    return None
#--------------------------------------------------------------------------------------------------------------------------------------------------
# Route function to add a new student --->                                          /student/add
@app.route('/student/add', methods=['POST'])
def add_student():
    # Method to only accept POST method
    if request.method == 'POST':
        student_data = request.json
        student_id = student_data.get('student_id')
        name = student_data.get('name')
        branch = student_data.get('branch')
        admission_year = student_data.get('admission_year')
        placed = student_data.get('placed', 'No')  # Default to 'No'
        semester_marks = student_data.get('semester_wise_marks')
        certified_skills = student_data.get('certified_skills', '')

        # if key and values aren't given
        if not student_id or not name or not branch or not admission_year or not semester_marks:
            return jsonify({"error": "Missing required student details"}), 400  # Bad Request - Missing Parameter

        # Validate data types
        error = validate_data_types_for_student_Add(student_data)
        if error:
            return jsonify({"error": error}), 400  # Bad Request - Invalid Data Types
        
        percentage = calculate_percentage(semester_wise_marks= semester_marks)
        cursor = conn.cursor()
        try:
            # Check if student ID already exists
            existing_student = get_student_data_from_snowflake(student_id)
            if existing_student:
                return jsonify({"error": "Student ID already exists"}), 409  # Conflict - ID already exists

            cursor.execute(
                "INSERT INTO STUDENT (ID, NAME, BRANCH, ADMYEAR, PLACED, SEM_WISE, PERCENTAGE, CERTIFIED_SKILLS) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (student_id, name, branch, admission_year, placed, semester_marks, percentage, certified_skills)
            )
            conn.commit()
        except Exception as e:
            return jsonify({"error": str(e)}), 500  # Internal Server Error
        finally:
            cursor.close()

        return jsonify({"message": "Student added successfully"}), 201  # Created
    
    # Handle other methods
    else:
        return jsonify({"error": "Method Not Allowed"}), 405  # Method Not Allowed

# Rote Function to delete the Student row --->                                          /student/remove
@app.route('/student/remove', methods = ['DELETE'])
def delete_student():
    # Method to only accept DELETE method
    if request.method == 'DELETE':
        student_id = request.args.get('student_id')
        password = request.args.get('password')

        if not student_id or not password:
            return jsonify({"error": "Missing student_id or password"}), 400 # Bad Request - Missing Parameter
        
        # Check for SQL injection patterns (simple heuristic check)
        if re.search(r"[\'\";]", student_id) or re.search(r"[\'\";]", password):
            return jsonify({"error": "Invalid input"}), 400  # Bad Request - Invalid input
        
        student_data, status_code = validate_student_credentials(student_id, password)

        if status_code != 200: # NOT OK
            return jsonify(student_data), status_code
        
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM STUDENT WHERE ID = %s", (student_id,))
            conn.commit()
            return jsonify({"message": "Student deleted successfully"}), 200 # OK
        except Exception as e:
            return jsonify({"error": str(e)}), 500 # Internal Server Error
        finally:
            cursor.close()
        
    # Handle other methods for /student/remove
    else:
        return jsonify({"error": "Method Not Allowed"}), 405 # Method Not Allowed


# Route Function to display Student Details --->                                        /student/details
@app.route('/student/details', methods=['GET'])
def display_student_details():
    if request.method == 'GET':
        student_id = request.args.get('student_id')
        password = request.args.get('password')

        # if key and values aren't given
        if not student_id or not password:
            return jsonify({"error": "Missing student_id or password"}), 400 # Bad Request - Missing Parameter
        
        # Check for SQL injection patterns (simple heuristic check)
        if re.search(r"[\'\";]", student_id) or re.search(r"[\'\";]", password):
            return jsonify({"error": "Invalid input"}), 400  # Bad Request - Invalid input
        
        student_data, status_code = validate_student_credentials(student_id, password)

        if status_code != 200:
            return jsonify(student_data), status_code
        
        display = {
            "Student ID":          html.escape(student_data[0]),
            "Name":                html.escape(student_data[1]),
            "Branch":              html.escape(student_data[6]),
            "Admission Year":      html.escape(student_data[2]),
            "Placed":              html.escape(student_data[3]),
            "Semester-wise Marks": html.escape(student_data[4]),
            "Percentage":          float(student_data[5]),
            "Certified Skills":    [html.escape(skill) for skill in student_data[7]]
        }
        return jsonify(display), status_code
    
    # Handle other methods for /student/details
    else:
        return jsonify({"error": "Method Not Allowed"}), 405 # Method Not Allowed   

# Route Function to display only the eligible companies for the specific student --->                   /student/eligibility
@app.route('/student/eligibility', methods=['GET'])
def student_eligibilty():
    if request.method == 'GET':
        student_id = request.args.get('student_id')
        password = request.args.get('password')

        # Validate input
        if not student_id or not password:
            return jsonify({"error": "Missing student_id or password"}), 400  # Bad Request - Missing Parameter

        # Check for SQL injection patterns (simple heuristic check)
        if re.search(r"[\'\";]", student_id) or re.search(r"[\'\";]", password):
            return jsonify({"error": "Invalid input"}), 400  # Bad Request - Invalid input

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
                "Branch":                     html.escape(company[4]),
                "Name":                       html.escape(company[1]),
                "Brief Description":          html.escape(company[2]),
                "Required Percentage":        float(company[3]),
                "Required Skills":            html.escape(company[5]),
                "Student Branch":             html.escape(student_data[6]),
                "Student Skills":             [html.escape(skill) for skill in student_skill_set],
                "Matching Skills":            html.escape(common_skills),
                "Student Percentage":         student_percentage,
                "Placement Likelihood":       likelihood
            }
            eligible_companies_list.append(company_display)

        return jsonify(eligible_companies_list)
    
    # Handle other methods for /student/eligibility
    else:
        return jsonify({"error": "Method Not Allowed"}), 405 # Method Not Allowed

# Route function to update a student's details --->                                                         /student/update_skills
@app.route('/student/update_skills', methods=['POST'])
def update_student_skills():
    student_id = request.json.get('student_id')
    password = request.json.get('password')
    new_skills = request.json.get('new_skills')

    # if key and values aren't given
    if not student_id or not password or not new_skills:
        return jsonify({"error": "Missing student_id, password, or new_skills"}), 400 # Bad Request - Missing Parameter

    student_data, status_code = validate_student_credentials(student_id, password)

    if status_code != 200:
        return jsonify({"error": "Invalid student ID or password"}), status_code

    if student_data[7] is None:
        updated_skills = new_skills
    else:
        student_data[7].extend(new_skills)
        updated_skills = list(set(student_data[7]))  # Remove duplicates

    # Update the student's skills in the database
    try:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE STUDENT SET CERTIFIED_SKILLS = '{', '.join(updated_skills)}' WHERE ID = '{student_id}'")
        conn.commit()
    except Exception as e:
        return jsonify({"error": str(e)}), 500 # Internal Server Error
    finally:
        cursor.close()

    return jsonify({"message": f"Skills updated successfully of student ID {student_id}"}), 200 # OK


@app.route('/student/apply', methods=['POST'])
def apply_to_company():
    student_id = request.json.get('student_id')
    password = request.json.get('password')
    company_id = request.json.get('company_id')

    # if key and values aren't given
    if not student_id or not password or not company_id:
        return jsonify({"error": "Missing student_id, password, or company_id"}), 400  # Bad Request - Missing Parameter

    # Validate student credentials
    student_data, status_code = validate_student_credentials(student_id, password)
    if status_code != 200:
        return jsonify(student_data), status_code

    # storing into variables
    student_place_status = student_data[3]
    student_percentage = float(student_data[5])

    # Check if the student is already placed
    if student_place_status == "Yes":
        return jsonify({"message": "You're Already Placed!"}), 200

    # Get company data
    company_data = get_specific_company_data_from_snowflake(company_id)
    if not company_data:
        return jsonify({"error": f"Company ID {company_id} doesn't exist"}), 404  # Not Found
    
    company_required_percentage = float(company_data[3])
    # Check if the student is eligible for the company
    if student_percentage < company_required_percentage:
        return jsonify({"error": "Student does not meet the required percentage for this company"}), 403  # Forbidden

    # Check matching skills
    matching_skills, _, _ = get_matching_skills(student_data[7], company_data[5])
    if not matching_skills:
        return jsonify({"error": "Student does not have the required skills for this company"}), 403  # Forbidden

    # Insert application record into the APPLICATION table
    try:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO APPLICATION (STUDENT_ID, COMPANY_ID) VALUES (%s, %s)",
            (student_id, company_id)
        )
        conn.commit()
    except Exception as e:
        return jsonify({"error": str(e)}), 500  # Internal Server Error
    finally:
        cursor.close()

    return jsonify({"message": "Application submitted successfully"}), 201  # Created


# Route function to add a new company --->                                                                  /company/add
@app.route('/company/add', methods=['POST'])
def add_company():
    company_id = request.json.get('company_id')
    name = request.json.get('name')
    brief_description = request.json.get('brief_description')
    required_percentage = request.json.get('required_percentage')
    branch = request.json.get('branch')
    required_skills = request.json.get('required_skills')

    # if key and values aren't given
    if not company_id or not name or not brief_description or not required_percentage or not branch or not required_skills:
        return jsonify({"error": "Missing required company details"}), 400  # Bad Request - Missing Parameter

    try:
        # Check if company ID already exists
        existing_company = get_specific_company_data_from_snowflake(company_id)
        if existing_company:
            return jsonify({"error": "Company ID already exists"}), 409  # Conflict - ID already exists

        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO COMPANY (ID, COMPANY_NAME, BRIEF_DESCRIPTION, REQUIRED_PERCENTAGE, BRANCH, REQUIRED_SKILLS) VALUES (%s, %s, %s, %s, %s, %s)",
            (company_id, name, brief_description, required_percentage, branch, required_skills)
        )
        conn.commit()
    except Exception as e:
        return jsonify({"error": str(e)}), 500  # Internal Server Error
    finally:
        cursor.close()

    return jsonify({"message": "Company added successfully"}), 201  # Created

# Route function to display the details of specific company --->                                             /company/details
@app.route('/company/details',methods=['GET'])
def display_company_details():
    company_id = request.args.get('company_id')
    company_password = request.args.get('company_password')
    
    # if key and values aren't given
    if not company_id or not company_password:
        return jsonify({"error": "Missing company_id or company_password"}), 400 # Bad Request - Missing Parameter
    
    company_data, status_code = validate_company_credentials(company_id, company_password)

    if status_code != 200: 
        return jsonify(company_data),status_code
    display_specific_company_details = {
        "Company ID":          company_data[0],
        "Branch":              company_data[4],
        "Name":                company_data[1],
        "Brief Description":   company_data[2],
        "Required Percentage": company_data[3],
        "Required Skills":     company_data[5]
    }
    return jsonify(display_specific_company_details), status_code

# Route function to delete a company by its ID --->                                                            /company/delete
@app.route('/company/delete', methods=['DELETE'])
def delete_company():
    company_id = request.json.get('company_id')
    company_password = request.json.get('company_password')

    # if key and values aren't given
    if not company_id or not company_password:
        return jsonify({"error": "Missing company_id or company_password"}), 400 # Bad Request - Missing Parameter

    company_data, status_code = validate_company_credentials(company_id, company_password)

    if status_code != 200:
        return jsonify({"error": "Invalid company ID or password"}), status_code

    # Delete the company from the database
    try:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM COMPANY WHERE ID = %s", (company_id,))
        conn.commit()
    except Exception as e:
        return jsonify({"error": str(e)}), 500 # Internal Server Error
    finally:
        cursor.close()

    return jsonify({"message": "Company deleted successfully"}), 200 # OK

# Route to display applications for a specific company --->                                         /company/applications
@app.route('/company/applications', methods=['GET'])
def display_company_applications():
    company_id = request.args.get('company_id')
    company_password = request.args.get('company_password')

    # if key and values aren't given
    if not company_id or not company_password:
        return jsonify({"error": "Missing company_id or company_password"}), 400 # Bad Request - Missing Parameter

    company_data, status_code = validate_company_credentials(company_id, company_password)
    if status_code != 200:
        return jsonify(company_data), status_code

    # Fetch applications for the company
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT APPLICATION_ID, STUDENT_ID FROM APPLICATION WHERE COMPANY_ID = %s", (company_id,)
        )
        applications = cursor.fetchall()
    except Exception as e:
        return jsonify({"error": str(e)}), 500  # Internal Server Error
    finally:
        cursor.close()

    if not applications:
        return jsonify({"message": "No applications found for this company"}), 404

    applications_list = []
    for application in applications:
        student_id = application[1]
        student_data = get_student_data_from_snowflake(student_id=student_id)
        matching_skills, student_skills, company_required_skills = get_matching_skills(student_data[7], company_data[5])
        application_display = {
            "Application ID": application[0],
            "Compamy ID" : company_id,
            "Student ID": application[1],
            "Student Name": student_data[1],
            "Branch": student_data[6],
            "Percentage": student_data[5],
            "Certified Skills": student_data[7],
            "Matched Skills":  matching_skills,
            "Admission Year" : student_data [2]
        }
        applications_list.append(application_display)

    return jsonify(applications_list), 200

# Route to accept or reject an application --->                                             /company/application/update
@app.route('/company/application/update', methods=['POST'])
def update_application_status():
    application_id = request.json.get('application_id')
    company_id = request.json.get('company_id')
    company_password = request.json.get('company_password')
    status = request.json.get('status')

    # if key and values aren't given
    if not application_id or not company_id or not company_password or not status:
        return jsonify({"error": "Missing application_id, company_id, company_password, or status"}), 400  # Bad Request - Missing Parameter

    if status not in ['accept', 'reject']:
        return jsonify({"error": "Invalid status. Must be 'accept' or 'reject'"}), 400  # Bad Request - Invalid Status

    company_data, status_code = validate_company_credentials(company_id, company_password)
    if status_code != 200:
        return jsonify(company_data), status_code

    # Fetch application details
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT STUDENT_ID FROM APPLICATION WHERE APPLICATION_ID = %s AND COMPANY_ID = %s", (application_id, company_id)
        )
        application = cursor.fetchone()
    except Exception as e:
        return jsonify({"error": str(e)}), 500  # Internal Server Error
    finally:
        cursor.close()

    if not application:
        return jsonify({"error": "Application not found"}), 404  # Not Found

    student_id = application[0]

    # If status is 'accept', update the student's 'PLACED' column
    if status == 'accept':
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE STUDENT SET PLACED = 'Yes' WHERE ID = %s", (student_id,)
            )
            conn.commit()
        except Exception as e:
            return jsonify({"error": str(e)}), 500  # Internal Server Error
        finally:
            cursor.close()
        
        message = "Application accepted and student status updated to 'Placed'"
    
    # If status is 'reject', simply acknowledge the rejection
    else:
        try:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE STUDENT SET PLACED = 'No' WHERE ID = %s", (student_id,)
            )
            conn.commit()
        except Exception as e:
            return jsonify({"error": str(e)}), 500  # Internal Server Error
        finally:
            cursor.close()
        message = "Application rejected"

    return jsonify({"message": message}), 200  # OK


#--------------------------------------------------------------------------------------------------------------------------------------------------

if __name__ == "__main__":
    if conn is None:
        print("Failed to connect to Snowflake. Exiting...")
    else:
        app.run(debug=True)