function(doc) {
  //Lookout for docs that are "devices".
  if (doc.doc_type == "device"){
    //Spit out all apps and a count of 1 to reduce.
    if((doc.apps_installed).length>0 && doc.first_created){
      for(var i=0; i<(doc.apps_installed).length; i++){           
        var d = new Date(doc.first_created*1000);
        emit([d.getFullYear(), d.getMonth(), doc.apps_installed[i]], 1);
      }
    }      
  }
}