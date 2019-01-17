#import Adafruit_DHT
import datetime
import time
import sys
import os
import config
import MySQLdb
import spidev
import urllib2
import cookielib
import pygal

from flask import Flask, redirect, url_for, render_template
from stat import *
from getpass import getpass

app = Flask(__name__)

# spi = spidev.SpiDev()
# spi.open(0,0)

@app.route("/")
def home():
	"""
	home page and display the record inserted in mysql
	"""
	tempature = None
	humidity = None
	date = None
	time = None
	moisture = None
	percentage = None
	try:
		# connction to my sql
		connection = MySQLdb.connect("localhost","root","root@123","sensor" )
		cursor = connection.cursor ()
		cursor.execute ("select * from sensor_readings_all")
		data = cursor.fetchall ()
		print "records from mysql",data
		for row in data :
			date = str(row[0]).split(" ")[0]
			time = str(row[0]).split(" ")[1]
			tempature = row[1]
			humidity = row[2]
			moisture = row[3]
			percentage = row[4]
		# close the cursor object
		cursor.close ()
		# close the connection
		connection.close ()
	except Exception as e:
		print str(e)
	return render_template('sample2.html',date=date,time= time,tempature=tempature,humidity=humidity,moisture=moisture,percentage=percentage)

@app.route('/read')
def insert_mysql():
	"""
	Reading the sensor reading like moisture sensor and temparature from rasperipy 
	and inserting that record in mysql
	"""
	# Open database connection
	try:
		print "entering read sensor data method"
		spi = spidev.SpiDev()
		spi.open(0,0)
		channel = 0
		db = MySQLdb.connect("localhost","root","root@123","sensor" )
		cursor = db.cursor()
		cursor.execute("DROP TABLE IF EXISTS sensor_readings_all")

		# Create table schema
		sql = """CREATE TABLE sensor_readings_all (
		         created_at TIMESTAMP,
		         temparature  FLOAT NOT NULL,
		         humidity FLOAT,
		         moisture FLOAT,
		         percentage FLOAT)"""  

		cursor.execute(sql)
		var = 2
		while var > 1:
			# reading humidity temparature reading
			humidity, temperature = Adafruit_DHT.read_retry(11, 4)
			#humidity, temperature = 200,27

			if ((channel>7)or(channel<0)):
				return redirect(url_for('home'))
			r = spi.xfer([1, (8+channel) << 4, 0])
			moisture = ((r[1]&3) << 8) + r[2]
			#moisture =480
			percentage = int(round(moisture/10.24))

			# if percentage is less then threshold send a message to mobile 
			if percentage < config.moisture_threshold:
				print "sending message to mobile"
				message = config.message
				number = config.number
				username = config.username
				passwd = config.passwd

				message = "+".join(message.split(' '))

				#logging into the sms site
				url ='http://site24.way2sms.com/Login1.action?'
				data = 'username='+username+'&password='+passwd+'&Submit=Sign+in'

				#For cookies
				cj= cookielib.CookieJar()
				opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))

				#Adding header details
				opener.addheaders=[('User-Agent','Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/37.0.2062.120')]
				try:
				    usock =opener.open(url, data)
				except IOError:
				    print "error in sending message"
				    #return()

				jession_id =str(cj).split('~')[1].split(' ')[0]
				send_sms_url = 'http://site24.way2sms.com/smstoss.action?'
				send_sms_data = 'ssaction=ss&Token='+jession_id+'&mobile='+number+'&message='+message+'&msgLen=136'
				opener.addheaders=[('Referer', 'http://site25.way2sms.com/sendSMS?Token='+jession_id)]
				try:
				    sms_sent_page = opener.open(send_sms_url,send_sms_data)
				except IOError:
				    print "error"
				    #return()
				print "successfully message has been sent" 
			ts = time.time()								
			timestamp = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    		# created_at,temperature,humidity ,moisture= timestamp,27,36,500
			created_at,moisture= timestamp,moisture
			# humidity, temperature ,created_at,moisture= Adafruit_DHT.read_retry(11, 4),timestamp,moisture
			print created_at, temperature,humidity, moisture, percentage
			print "inserting record"
			sql = "INSERT INTO sensor_readings_all(created_at,temparature, humidity,moisture,percentage)VALUES ('%s','%d', '%d', '%d','%d')" % (created_at,temperature, humidity,moisture,percentage)
			try:
			   # Execute the SQL command
			   print "executing insert command"
			   cursor.execute(sql)
			   # Commit your changes in the database
			   db.commit()
			   var +=1
			   print "inserted"
			   if var == 3:
			   	break
			except:
			   # Rollback in case there is any error
			   print "exeption occured"
			   db.rollback() 

		# disconnect from server
		db.close()

	except Exception as e:
		print e
	
	return redirect(url_for('home'))

@app.route('/chart')
def chart_plot():
	"""
	Plot a graph
	"""
	try:
		spi = spidev.SpiDev()
		spi.open(0,0)
		i = 0
		channel = 0
		temperatures = []
		humiditys = []
		moistures= []
		while i <10:
			# humidity, temperature = 2,10
			humidity, temperature = Adafruit_DHT.read_retry(11, 4)
			temperatures.append(temperature)
			humiditys.append(humidity)
			if ((channel>7)or(channel<0)):
				return redirect(url_for('home'))
			r = spi.xfer([1, (8+channel) << 4, 0])
			moisture = ((r[1]&3) << 8) + r[2]
			# moisture = 200
			moistures.append(moisture)
			print 'Temp: {0:0.1f} C  Humidity: {1:0.1f} %'.format(temperature, humidity)
			i +=1

		line_chart = pygal.Line()
		line_chart.title = 'Plant health report'
		line_chart.x_labels = map(str, range(1, 10))
		line_chart.add('temparature', temperatures)
		line_chart.add('humidity', humiditys)
		line_chart.add('moisture',      moistures)
		chart = line_chart.render(is_unicode=True)
		return render_template('chart.html', chart=chart )
	except Exception as e:
		print e
	return redirect(url_for('home'))

if __name__ == "__main__":
	app.run(host='0.0.0.0',debug=True)
