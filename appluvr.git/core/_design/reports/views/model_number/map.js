function(doc) {
  //lookout for docs that are "devices"	
  if (doc.doc_type == "device"){
  	  //spit out model and number and a marker include docs.
      emit([doc.model,doc.number], doc._id);
      emit([doc.number,doc.model], doc._id);
  } 
}