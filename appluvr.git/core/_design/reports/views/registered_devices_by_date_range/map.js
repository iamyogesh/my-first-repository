function(doc) {
  //Lookout for docs that are "devices".
  if (doc.doc_type == "device"){
    //Spit out all devices that have a created date and a count of 1 to reduce.
    if(doc.first_created){
        var d = new Date(doc.first_created*1000);
        emit([d.getFullYear(), d.getMonth(), doc.make.toUpperCase(), doc.model.toUpperCase(), doc.number.toUpperCase()], 1);
    }
  }
}