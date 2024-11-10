%
% ���������
%
clear all;
close all;

f = @(x) x^3-x-1;      % ԭ����
g = @(x) (x+1)^(1/3);  % �������� 
maxit = 10;            % ����������

fprintf('��������: g=%s\n', char(g));

fvalue = zeros(maxit,1);

x = 1.5; % ȡ�е�Ϊ������ʼֵ
for k = 1 : maxit
    x = g(x);
    fvalue(k) = abs(f(x));
    fprintf('k=%d, x=%.4f, f(x)=%.2e\n',k, x, fvalue(k));
end

% ��ͼ������ֵ�½�����
semilogy(1:maxit, fvalue, 'ob-')
xlabel('k'); ylabel('|f(x)|');
title('����ֵ�½�����')