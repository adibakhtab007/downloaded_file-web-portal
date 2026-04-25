# Secure File Portal — End User Guide

## 1. Purpose
This guide explains how normal portal users can register, log in, access folders and files, manage their profile, and recover access when needed.

## 2. Main End-User Pages
- Login: `/auth/login/`
- Register: `/auth/register/`
- OTP Verification: `/auth/otp/`
- Unlock Account: `/auth/unlock/`
- User Portal: `/portal/`
- My Profile: `/portal/profile/`
- Change Password: `/portal/password/change/`

## 3. Registering a New Account
1. Open the **Register** page.
2. Enter your required details.
3. Submit the form.
4. Your account will stay in **Pending Approval** until an administrator approves it.
5. After approval, you can log in normally.

## 4. Logging In
1. Open the **Login** page.
2. Enter your email address and password.
3. Click **Sign in**.
4. If the password is correct, the portal sends an OTP code to your email.
5. Open your email and enter the OTP on the OTP Verification page.
6. After successful OTP verification, you are redirected to your portal.

## 5. Password Visibility Toggle
On the login page, the password field supports a show/hide eye icon.
- Click the eye icon once to show the password.
- Click it again to hide the password.

## 6. If You Enter a Wrong Password
- The portal can reject the login attempt.
- Repeated wrong password attempts may block the account temporarily.
- If blocked, use the unlock flow or contact an administrator.

## 7. OTP Notes
- OTP is required after correct email and password entry.
- OTP has an expiry time.
- OTP also has a limited number of attempts.
- If OTP expires, go back and log in again to generate a new OTP.

## 8. Unlocking a Blocked Account
If you cannot log in because the account is blocked:
1. Click **Forgot Password?** on the login page.
2. Go to the **Unlock Account** page.
3. Enter your email and your security answers.
4. If the answers are correct, the portal continues the unlock process.
5. Follow the next steps shown by the portal.

## 9. Using the User Portal
After login, normal users land on the **User Portal**.

Typical actions:
- see folders you are allowed to access
- open folders
- view files inside allowed folders
- download files you are authorized to download

You will only see folders and files that have been granted to you.

## 10. Downloading Files
1. Open an allowed folder.
2. Click the file you want to download.
3. The portal checks access first.
4. If access is valid, the file download starts.

## 11. My Profile
On **My Profile**, you can usually view:
- full name
- email address
- password expiry date/time

From this page, you can also go to password change.

## 12. Changing Your Password
1. Open **My Profile**.
2. Click **Change Password**.
3. Enter the required details.
4. Complete the change.

Important rules commonly applied by the portal:
- password expiry is enforced
- password reuse control may apply
- complexity rules may apply

## 13. Password Expired
If your password expires:
- you may be redirected to the expired-password reset flow
- complete the reset process before normal login continues

## 14. Common Status Meanings
- **Pending Approval**: registration submitted, waiting for admin approval
- **Approved**: account is active and usable
- **Blocked**: blocked due to failed login attempts
- **Security Blocked**: blocked due to security/unlock failures
- **Disabled - Password Expired**: password must be reset
- **Disabled by Admin**: administrator manually disabled the account
- **Rejected**: registration was rejected
- **Deleted**: account was removed from active use

## 15. What To Do If You Do Not Receive OTP Email
1. Check spam/junk folder.
2. Wait a short time and retry.
3. Confirm your registered email is correct.
4. Contact an administrator if the issue continues.

## 16. Basic Security Advice for Users
- Do not share your OTP code.
- Do not share your portal password.
- Log out after use.
- Use a strong password.
- Report unexpected access issues to an administrator.

## 17. Quick Troubleshooting
### Problem: Login says invalid credentials
- Check email spelling
- Check password carefully
- Use the password eye icon if needed

### Problem: OTP expired
- Log in again to generate a new OTP

### Problem: Account blocked
- Use **Forgot Password / Unlock Account**
- Or contact an administrator

### Problem: Cannot see expected folders
- Folder access may not be granted yet
- Contact an administrator

### Problem: Cannot download a file
- You may not have permission
- Or the file may no longer be active in the portal

## 18. Contact Administrator
Contact your administrator when:
- registration is still pending for too long
- you do not have access to needed folders
- OTP mail is not arriving
- your account is blocked and unlock does not work
- a file is missing or download fails
