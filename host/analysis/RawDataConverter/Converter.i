///* RawDataConverter.i */
// %module RawDataConverter
// %{
// /* Put header files here or function declarations like below */
// extern int fact(int n);
// extern int my_mod(int x, int y);
// extern char *get_time();
// %}
// 
// extern int fact(int n);
// extern int my_mod(int x, int y);
// extern char *get_time();
%include "std_string.i"

%module Converter
%{
  #include "Converter.h"
%}

%include Converter.h