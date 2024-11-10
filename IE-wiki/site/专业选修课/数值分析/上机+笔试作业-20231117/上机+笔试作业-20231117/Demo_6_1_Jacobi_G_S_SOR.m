%
%  Jacobi, G-S �� SOR ����
%
clear all;
close all;

%A = [2 -1 0; -1 3 -1; 0 -1 2];
%b = [1; 8; -5];
A = [6 -1 -1; -5 10 -2; -2 -1 3];
b = [6.2; 8.1; 3.2];
x0 = [0; 0; 0];
tol = 1e-5;
itermax = 100;

D = diag(diag(A));  % A �ĶԽ��߲���
L = D - tril(A);    % -L Ϊ A ���ϸ������ǲ���
U = D - triu(A);    % -U Ϊ A ���ϸ������ǲ���

% Jacobi ����
fprintf('Jacobi: \n')
x = x0;  
for iter= 1 : itermax
    x = D \ ( (L+U)*x + b );
    relres = norm(b - A*x) / norm(b); 
    fprintf('iter=%d, relres=%.2e, x=[%.4f, %.4f, %.4f]\n',iter, relres,x(1),x(2),x(3))
    if (relres<tol), break, end
end

% G-S ����
fprintf('\nG-S: \n')
x = x0; 
for iter = 1 : itermax
    x = (D-L) \ ( U*x + b );
    relres = norm(b - A*x) / norm(b); 
    fprintf('iter=%d, relres=%.2e, x=[%.4f, %.4f, %.4f]\n',iter, relres,x(1),x(2),x(3))
    if (relres<tol), break, end
end

% SOR ����
fprintf('\nSOR: \n')
omega = 1.1;  % ����
x = x0; 
for iter = 1 : itermax
    x = (D-omega*L) \ ( ((1-omega)*D + omega*U)*x + omega*b );
    relres = norm(b - A*x) / norm(b); 
    fprintf('iter=%d, relres=%.2e, x=[%.4f, %.4f, %.4f]\n',iter, relres,x(1),x(2),x(3))
    if (relres<tol), break, end
end

