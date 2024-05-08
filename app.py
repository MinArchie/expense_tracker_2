import os
from flask import Flask, flash, jsonify, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from jinja2 import Template
from helper import login_required

import Queries as q

app = Flask(__name__)

app.config["DEBUG"] = False

db = q.create_connection("app_database.db")

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_FILE_DIR"] = "./flask_session_cache"
Session(app)


#route for root url
@app.route('/', methods = ['GET'])
def index():
	return render_template("index.html")

# registration page sql functions. 
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        
        username = request.form.get("username")
        existing_user_query = "SELECT id FROM users WHERE uname = :username"
        existing_user = q.sql_select_query(db, existing_user_query, {"username": username})
        
        if existing_user:
            flash("Username already exists. Please choose a different username.")
            return render_template("register.html", show_forms=True)
        
        
        if request.form.get("password") != request.form.get("confirmPassword"):
            flash("Passwords do not match. Please try again.")
            return render_template("register.html", show_forms=True)

        initial_balance = 0

        sql_query = "INSERT INTO users (uname, password, balance) VALUES (:username, :password, :balance)"
        q.sql_insert_query(db, sql_query, {"username": username, "password": generate_password_hash(request.form.get("password")), "balance": initial_balance})
        
        return redirect("/")
    
    else:
        return render_template("register.html", show_forms=True)




# login page, handle login requests
@app.route('/login', methods = ['GET','POST'])
def login():
	if request.method == 'POST':
		username = request.form.get("username")
		pd = request.form.get("password")
		sql_query = "SELECT * from users where uname = :username"
		rows = q.sql_select_query(db,sql_query, dict(username = username))
		if(len(rows) < 1):
			flash("Username does not exists",'error')
		else:
			user_password = rows[0]["password"]
			print(user_password)
			print(generate_password_hash(pd))
			if(not check_password_hash(user_password,pd)) :
				flash("Incorrect Password",'error')
			else:
				session["user_id"] = rows[0]["id"]
				return redirect("/")
	return render_template("login.html", show_forms=True)



# logout requests
@app.route('/logout',methods = ['GET','POST'])
@login_required
def logout():
	session.clear()
	return redirect("/")



# transaction requets
@app.route('/transaction',methods = ['GET','POST'])
@login_required
def transaction():
	pre_existing_reasons = ["Income", "Groceries", "Utilities", "Rent", "Entertainment", "Transportation", "Food"]

	return render_template("transaction.html",  reasons=pre_existing_reasons)


# edit existing transaction; can change reason, amount, and type
@app.route('/edit_transaction/<int:transaction_id>', methods=['GET', 'POST'])
@login_required
def edit_transaction(transaction_id):
    if request.method == 'POST':
        new_reason = request.form.get("reason")
        new_amount = float(request.form.get("amount"))
        
        
        old_transaction_query = "SELECT amount FROM transactions WHERE id = :transaction_id"
        old_transaction_variables = {"transaction_id": transaction_id}
        old_transaction = q.sql_select_query(db, old_transaction_query, old_transaction_variables)
        
        if old_transaction:
            old_amount = old_transaction[0]["amount"]
            
            sql_query = "UPDATE transactions SET reason = :reason, amount = :amount WHERE id = :transaction_id"
            variables = {"reason": new_reason, "amount": new_amount, "transaction_id": transaction_id}
            q.sql_insert_query(db, sql_query, variables)

            user_id = session["user_id"]
            user_balance_query = "SELECT balance FROM users WHERE id = :user_id"
            user_balance_variables = {"user_id": user_id}
            user_balance = q.sql_select_query(db, user_balance_query, user_balance_variables)
            
            if user_balance:
                current_balance = user_balance[0]["balance"]
                
                difference = new_amount - old_amount
                
                new_balance = current_balance + difference
                update_balance_query = "UPDATE users SET balance = :new_balance WHERE id = :user_id"
                update_balance_variables = {"new_balance": new_balance, "user_id": user_id}
                q.sql_insert_query(db, update_balance_query, update_balance_variables)
                
                return redirect("/statement")
        
        flash("Transaction not found or user balance not found", "error")
        return redirect("/statement")

    else:
        sql_query = "SELECT * FROM transactions WHERE id = :transaction_id"
        variables = {"transaction_id": transaction_id}
        transaction = q.sql_select_query(db, sql_query, variables)
        
        if transaction:
            pre_existing_reasons = ["Income", "Groceries", "Utilities", "Rent", "Entertainment", "Transportation", "Food"]
            return render_template("edit_transaction.html", transaction=transaction[0], reasons=pre_existing_reasons)
        else:
            flash("Transaction not found", "error")
            return redirect("/statement")



# delete existing transaction
@app.route('/delete_transaction/<int:transaction_id>', methods=['GET'])
@login_required
def delete_transaction(transaction_id):
    sql_query = "SELECT amount FROM transactions WHERE id = :transaction_id"
    variables = {"transaction_id": transaction_id}
    deleted_transaction = q.sql_select_query(db, sql_query, variables)

    if deleted_transaction:
        deleted_amount = deleted_transaction[0]["amount"]

        user_id = session["user_id"]
        sql_query = "SELECT balance FROM users WHERE id = :user_id"
        variables = {"user_id": user_id}
        current_balance = q.sql_select_query(db, sql_query, variables)

        if current_balance:
            current_balance = current_balance[0]["balance"]
            new_balance = current_balance + deleted_amount

            sql_query = "UPDATE users SET balance = :new_balance WHERE id = :user_id"
            variables = {"new_balance": new_balance, "user_id": user_id}
            q.sql_insert_query(db, sql_query, variables)

        sql_query = "DELETE FROM transactions WHERE id = :transaction_id"
        variables = {"transaction_id": transaction_id}
        q.sql_insert_query(db, sql_query, variables)

    return redirect("/statement")





# seperate functions for credit and debit
# credit -> adds amount to database
@app.route('/credit', methods=['GET', 'POST'])
def credit():
    if request.method == 'POST':
        user_id = session["user_id"]
        amount = float(request.form.get("amount"))
        reason = request.form.get("reason")
        
        if reason == "custom":
            reason = request.form.get("customReason")

        type_of_transaction = "C"
        sql_query = "INSERT INTO transactions(user_id, reason, type, amount) VALUES (:user_id, :reason, :type, :amount)"
        variable = dict(user_id=session["user_id"], reason=reason, type=type_of_transaction, amount=amount)
        q.sql_insert_query(db, sql_query, variable)
        
        users_balance = "SELECT balance FROM users WHERE id = :user_id"
        rows = q.sql_select_query(db, users_balance, dict(user_id=user_id))
        balance = rows[0][0] 
        
        balance += amount
        
        sql_query = "UPDATE users SET balance = :balance WHERE id = :user_id"
        variable = dict(balance=balance, user_id=user_id)
        q.sql_insert_query(db, sql_query, variable)
        
    return redirect("/transaction")


# debit -> subtracts amount from database
@app.route('/debit', methods=['GET', 'POST'])
def debit():
    if request.method == 'POST':
        user_id = session["user_id"]
        amount = float(request.form.get("amount"))
        reason = request.form.get("reason")
        
        if reason == "custom":
            reason = request.form.get("customReason")

        type_of_transaction = "D"
        sql_query = "INSERT INTO transactions(user_id, reason, type, amount) VALUES (:user_id, :reason, :type, :amount)"
        variable = dict(user_id=session["user_id"], reason=reason, type=type_of_transaction, amount=amount)
        q.sql_insert_query(db, sql_query, variable)
        
        users_balance = "SELECT balance FROM users WHERE id = :user_id"
        rows = q.sql_select_query(db, users_balance, dict(user_id=user_id))
        balance = rows[0][0] 
        
        balance -= amount
        
        sql_query = "UPDATE users SET balance = :balance WHERE id = :user_id"
        variable = dict(balance=balance, user_id=user_id)
        q.sql_insert_query(db, sql_query, variable)
        
    return redirect("/transaction")







# display the transactions in statement page
@app.route('/statement', methods=['GET'])
@login_required
def statement():
    user_id = session["user_id"]

    sql_query = "SELECT * FROM transactions WHERE user_id = :user_id"
    variables = {"user_id": user_id}
    rows = q.sql_select_query(db, sql_query, variables)

    sql_query = "SELECT balance FROM users WHERE id = :user_id"
    variables = {"user_id": user_id}
    balance_row = q.sql_select_query(db, sql_query, variables)

    balance = 0

    for record in rows:
        if record["type"] == "C":
            balance += record["amount"]
        elif record["type"] == "D":
            balance -= record["amount"]

    return render_template("statement.html", records=rows, balance=balance)


