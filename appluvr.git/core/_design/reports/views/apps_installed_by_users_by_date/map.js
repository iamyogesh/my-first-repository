function(doc) {

  //lookout for docs that are "devices" 
  if (doc.doc_type == "device"){
      //Get installed apps count.
      var ctr = 0;

      try{
        if((doc.apps_installed).length>0){
            ctr = (doc.apps_installed).length;
        }
      }catch(e){ctr=0;}  
      var d = new Date(doc.first_created*1000);
      emit([d.getFullYear(), d.getMonth(), doc._id], {number_of_apps:ctr});
  }

}