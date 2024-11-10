% 
% Bisection for nonlinear equation
%
clear all; 
close all;

f = @(x) x.^3 - x - 1; %anonymous function
a = 1; b = 2;
tol = 1e-3;       % tolerance 
maxit = 100;      % maximum iteration number

fa = f(a); fb = f(b);
k = 1;
for k = 1 : maxit
    x = (a+b)/2;
    fx = f(x);
    fprintf('k=%d, a/fa=%.4f/%.4f, b/fb=%.4f/%.4f, x/fx=%.4f/%.4f\n', ...
        k, a, fa, b, fb, x, fx);
    if ( abs(fx)<tol || b-a<tol )
        break;
    end
    if ( fx*fa < 0 )
        b = x; fb = fx;
    else
        a = x; fa = fx;
    end
end

