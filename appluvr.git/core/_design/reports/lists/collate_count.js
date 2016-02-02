function (head, req) {

  //Placeholder for result.
  var fb_status = null, apps_status = null, row, ctr = 0;
  var final_result = { data:null, total:null};
  var jObj = { fb_apps: 0, nfb_napps: 0, nfb_apps: 0, fb_napps: 0};

  //Process each row/doc, do fb + read apps status and total counting.
  while (row = getRow()) {    
    //Mark FB status.
    fb_status = row.value["fb_login"];

    //Mark Read Apps status.
    if(row.value["_id"]=="null"){
      apps_status = false;
    } else {
      apps_status = (row.doc["read_apps"]=="true" || row.doc["read_apps"])?true:false;
    }
    
    //Mark counters based on values of FB and Read Apps status.    
    if(fb_status && apps_status){
      jObj.fb_apps += 1;
    }else if (!fb_status && !apps_status) {
      jObj.nfb_napps += 1;
    } else if (!fb_status && apps_status) {
      jObj.nfb_apps += 1;
    } else {
      jObj.fb_napps += 1;
    }

    //Count total as well.
    ctr++;
  }
  
  //Final Output.
  final_result.data = jObj;
  final_result.total = ctr;  
  send(toJSON(final_result));

}