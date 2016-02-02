var startMonth,startYear,endMonth,endYear;

//Fires off on document load.
$(document).ready(function(){

	//Load all report templates.
	load_report_templates();	
		
	$('#users_tag').bind('click', function(event) {
		//Clear the right pane.
		hideReportingElements();
		//Check the date range.		 
		if(isRangeOK()){
			//Load Total Users
			load_report(props.total_users_count);
			//Load All Users
			load_report(props.all_users_count);
			//Load New Users
			load_report(props.new_users_count);
			//Load User Personalization
			load_report(props.user_personalization_report_config);
			//Menu Colors
			resetBorderForUL();
			$(this).css('border-left', '4px solid #CC0000');
		}		
	});	

	$('#devices_tag').bind('click', function(event) {
		//Clear the right pane.
		hideReportingElements();
		//Check the date range.		 
		if(isRangeOK()){
			//Load Total Devices
			load_report(props.total_devices_count);
			//Load All Devices
			load_report(props.all_devices_count);
			//Load New Devices
			load_report(props.new_devices_count);
			//Load Registered Devices
			load_report(props.registered_devices_config);
			//Menu Colors
			resetBorderForUL();
			$(this).css('border-left', '4px solid #CC0000');
		}
	});	

	$('#apps_tag').bind('click', function(event) {
		//Clear the right pane.
		hideReportingElements();
		//Check the date range.		 
		if(isRangeOK()){
			//Load Top 50 Apps and Counts
			load_report(props.top_50_apps_report_config);
			//Load Apps Installed by Devices
			load_report(props.apps_installed_by_device_config);
			//Menu Colors
			resetBorderForUL();
			$(this).css('border-left', '4px solid #CC0000');
		}
	});	

});

function resetBorderForUL(){
	$("#category-menu").children("li").each(function(){
	    $($(this).children("a")).css('border-left', '4px solid white');
	});
}

//Check date range.
function isRangeOK(){
	if(!startMonth||!startYear||!endMonth||!endYear){
		alert("Please pick start and end dates!"); return false;
	}

	if( new Date(startYear, startMonth) >= new Date(endYear, endMonth)){
		alert("Please pick an End Date beyond the Start Date!"); return false;	
	}
	return true;
}


//Hide all the reporting elements.
function hideReportingElements(){
	//Find and remove all elements as needed.
	$('table[id^="table"]').remove();
	$('span[id^="no_data"]').remove();
	$("#right-pane").children("div").each(function(){
	    $(this).hide();
	});
}

//Load all reporting templates and append to main body.
function load_report_templates(){
	//Load the template definition file, inject all those templates at the end of the document.	 
	var url = "/"+props.db_name+"/_design/"+props.design_doc+props.report_templates_url;
	 $.ajax({
        'async': false,
        'cache': false,
        'global': false,
        'url': url,
        'dataType': "text",
        'success': function (templates) {
            $('body').append(templates);
        }
    });
}

function toId(id){return "#"+id;}

function capitalize(str){
	return str.toLowerCase().replace(/\b[a-z]/g, function(letter) { return letter.toUpperCase(); });
}

//Top 50 Apps Report.
function load_report(config){
	
	//Animation Control.
	$(toId(config.container_id)).show();
    $(toId(config.loading_id)).show();

    //Form proper URL.
	var report_url = "/"+props.db_name+"/_design/"+props.design_doc+config.url;
	var params = "";	
	if(config.range) params=params+"startkey=["+startYear+","+startMonth+"]&endkey=["+endYear+","+endMonth+"]";
	if(config.till_end_date) params=params+"startkey=[]&endkey=["+endYear+","+endMonth+"]";
	if(config.group_level) params=params+"&group_level="+config.group_level;
	if(config.include_docs) params=params+"&include_docs=true";	

	//Populate the table, LAZY load.
	$.ajax({url: report_url, data: params, cache: false}).done(function( data ) {

		//Format data using function, if specified.
		if(config.format_data) 	data = executeFunctionByName(config.format_data,window,data);			

		//Check for empty data and handle accordingly.		
		var properData = true;
		if(config.template == "two_col_report_template"){
			if(data.data.length==undefined || data.data.length==0){properData = false;}
		}else{
			if(data.rows.length==0){properData = false;}
		}		

		if(properData){
			//Use underscore to convert the template to a 'template' object
			var reportTemplate = _.template($(toId(config.template)).text());
			//Use the template object to output our html.
			var html = reportTemplate({'config': config, 'result' : data});
			$(toId(config.container_id)).append(html);
			if(config.template == "two_col_report_template"){						
				//Apply the tableSorter plugin, for all the magic.
				$(toId(config.table_name)).tablesorter({ debug:false, sortList:config.sort_list})
		        .tablesorterPager({ container:$(toId(config.pager_name)), positionFixed:false, size:config.paging_options[0] })
		        .tablesorterFilter({ filterContainer:$(toId(config.fltr_name)), filterClearContainer:$(toId(config.clear_name)), filterColumns:config.filter_columns, filterCaseSensitive:false });
	        }
        }else{
        	$(toId(config.container_id)).append(props.no_data_message);
        }
        
        //Animation Control.
        $(toId(config.loading_id)).hide();        
        $(toId(config.table_name)).show();
        $('#Total_'+config.table_name).show();
	});
	
}

function executeFunctionByName(functionName, context /*, args */) {
    var args = Array.prototype.slice.call(arguments, 2);
    var namespaces = functionName.split(".");
    var func = namespaces.pop();
    for (var i = 0; i < namespaces.length; i++) {
        context = context[namespaces[i]];
    }
    return context[func].apply(context, args);
}

function formatUserPersonalization(data){
	
	data.data = [
		{name: "FB Login, Apps Read", count: data.data.fb_apps},
		{name: "No FB Login, Apps Read", count: data.data.nfb_apps},
		{name: "FB Login, No Apps Read", count: data.data.fb_napps},
		{name: "No FB Login, No Apps Read", count: data.data.nfb_napps}
	];

	return data;
}

function formatRegisteredDevices(data){
	
	for(var i=0; i<data.data.length; i++){
		var str = data.data[i].name.split(" ");
		str[0] = capitalize(str[0]);
		data.data[i].name = str.join(" ");		
    }
    return data;
}

function formatViewResults(data){
	
	return $.parseJSON(data);
}



$(function() {
    $('.start-date-picker').datepicker( {
        changeMonth: true,
        changeYear: true,
        showButtonPanel: true,
        dateFormat: 'MM yy',
        onClose: function(dateText, inst) { 
            startMonth = $("#ui-datepicker-div .ui-datepicker-month :selected").val();
            startYear = $("#ui-datepicker-div .ui-datepicker-year :selected").val();
            $(this).datepicker('setDate', new Date(startYear, startMonth, 1));
        }
    });
});

$(function() {
    $('.end-date-picker').datepicker( {
        changeMonth: true,
        changeYear: true,
        showButtonPanel: true,
        dateFormat: 'MM yy',
        onClose: function(dateText, inst) { 
            endMonth = $("#ui-datepicker-div .ui-datepicker-month :selected").val();
            endYear = $("#ui-datepicker-div .ui-datepicker-year :selected").val();
            $(this).datepicker('setDate', new Date(endYear, endMonth, 1));
        }
    });
});