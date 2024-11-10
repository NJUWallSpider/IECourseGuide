% 
% Steffenson ����
%

clear all; 
close all;

f = @(x) x^3-x-1;
g = @(x) x^3-1;

fprintf('True solution: x = %.8f\n',fzero(f,[1,2])) %�����Ժ�����[1,2]�ĸ�

n = 6; % ���õ�������
x = 1.5; % ������ʼֵ

% ���������
fprintf('��ͨ���������\n')
for k = 1 : n
    x = g(x);
    fprintf('k=%d, x=%.8g\n',k,x);
end
   
% Steffenson ����
x = 1.5; % ������ʼֵ
fprintf('===================\n');
fprintf('Steffenson ����\n');
for k = 1 : n
    x1 = g(x); x2 = g(x1);
    x = x - (x1-x)^2/(x2-2*x1+x);
    fprintf('k=%d, x=%.8f\n',k,x);
end