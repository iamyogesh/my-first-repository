function(doc){
  //Process only "user" docs.
  if(doc.doc_type == "user"){
    
    //Don't process if no First Created date is found, just leave.
    if(!doc.first_created || doc.first_created == null) return;    

    //Mark FB Login status
    var fb_login = false, userHasNoDevices = true;   
    if(doc.fb_id)
    	fb_login=true;
    
    //Link and output all associated devices for this user to list for processing.
    var links = doc.links;
    var udid = null;
    var d = new Date(doc.first_created*1000);
    for(var i=0;i<links.length;i++){
      if(links[i].rel == 'device'){
        udid = links[i].href;
        if(udid && doc.first_created){          
          userHasNoDevices=false;          
          emit([d.getFullYear(), d.getMonth(), doc._id], {_id:udid, fb_login:fb_login});
        }
      }
    }

    //Even if a user has no devices it needs to get listed.
    if(userHasNoDevices && doc.first_created){
      emit([d.getFullYear(), d.getMonth(), doc._id], {_id:"null", fb_login:fb_login});
    }
  }
}