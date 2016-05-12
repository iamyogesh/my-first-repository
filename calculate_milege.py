def calculate_milege(amount, petrol_price,no_km_run):

	no_of_letres = amount/petrol_price
	milege = no_km_run/ no_of_letres
	return milege

amount = input("enter the amount spend on petrol\n")
petrol_price = input("enter the petrl price\n")
no_km_run = input("the number of km your bike run\n")

print calculate_milege(amount,petrol_price,no_km_run)

