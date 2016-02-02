function(doc) {

  //lookout for docs that are "devices"	
  if (doc.doc_type == "device"){
  	  //spit out make, model and number and a marker for reduce.js
      emit([doc.make,doc.model,doc.number], 1);
  } 
}