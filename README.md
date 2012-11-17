A simple JavaScript build tool that essentially concatenates the files and minifies it. 

This program has two modes: The debug mode and the production mode. 
Debug mode can be turned on with the -d flag. 

In debug mode the output file will be 'document.write's which put the script tags in in order. 

In production mode, the output file will be concatenated with all contents of required files in order and minified (using YUI compressor). 


Example for including files: 
<pre>
	//=> Parent Utils Stack
	
	function () {
		...
	}
</pre>

Example for the HTML

<pre>
<!DOCTYPE HTML>
<html lang="en-US">
<head>
	<meta charset="UTF-8">
	<title></title>
	<script type="text/javascript" src="output.js" data-src="entry-point.js"></script>
</head>
<body>
	
</body>
</html>
</pre>