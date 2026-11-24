import { Navigate, NavLink, Route, Routes, useMatch } from "react-router-dom";
import { useAuth } from "./auth.jsx";
import { LogoMark } from "./site.jsx";
import Landing from "./pages/Landing.jsx";
import Login from "./pages/Login.jsx";
import Signup from "./pages/Signup.jsx";
import PublicForm from "./pages/PublicForm.jsx";
import Results from "./pages/Results.jsx";
import { AdminAudit, AdminCourses, AdminCustomers, AdminPlatform, AdminUsers } from "./pages/Admin.jsx";
import { Assignment, Course, TeacherHome } from "./pages/Teacher.jsx";
import Run from "./pages/Run.jsx";
import Pair from "./pages/Pair.jsx";
import Review from "./pages/Review.jsx";
import { MyCase, MyFlags, MySubmission } from "./pages/Student.jsx";

const HOME = { admin: "/admin/platform", teacher: "/courses", student: "/me" };

const NAV = {
  admin: [["/admin/platform", "Platform"], ["/admin/customers", "Customers"], ["/admin/users", "Users"], ["/admin/courses", "Courses"], ["/admin/audit", "Audit log"]],
  teacher: [["/courses", "My courses"]],
  student: [["/me", "My flags"]],
};

export default function App() {
  const { user, ready, logout } = useAuth();
  const publicForm = useMatch("/f/:token");
  const publicResults = useMatch("/results");
  // a shared form and the results page work the same whether or not the visitor is logged in
  if (publicForm) return <Routes><Route path="/f/:token" element={<PublicForm />} /></Routes>;
  if (publicResults) return <Results />;
  if (!ready) return null;
  if (!user) {
    return (
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route path="/login" element={<Login />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="*" element={<Navigate to="/login" replace />} />
      </Routes>
    );
  }

  return (
    <div className="shell">
      <header className="topbar">
        <span className="brand"><LogoMark size={26} />CodeTwin</span>
        <nav>
          {NAV[user.role].map(([to, label]) => (
            <NavLink key={to} to={to}>{label}</NavLink>
          ))}
        </nav>
        <span className="who">
          {user.full_name} · {user.role}
          <button className="link" onClick={logout}>Sign out</button>
        </span>
      </header>
      <main>
        <Routes>
          {user.role === "admin" && (
            <>
              <Route path="/admin/platform" element={<AdminPlatform />} />
              <Route path="/admin/customers" element={<AdminCustomers />} />
              <Route path="/admin/users" element={<AdminUsers />} />
              <Route path="/admin/courses" element={<AdminCourses />} />
              <Route path="/admin/audit" element={<AdminAudit />} />
            </>
          )}
          {user.role === "teacher" && (
            <>
              <Route path="/courses" element={<TeacherHome />} />
              <Route path="/courses/:courseId" element={<Course />} />
              <Route path="/assignments/:assignmentId" element={<Assignment />} />
              <Route path="/runs/:runId" element={<Run />} />
              <Route path="/pairs/:pairId" element={<Pair />} />
              <Route path="/reviews/:reviewId" element={<Review />} />
            </>
          )}
          {user.role === "student" && (
            <>
              <Route path="/me" element={<MyFlags />} />
              <Route path="/me/cases/:reviewId" element={<MyCase />} />
              <Route path="/submissions/:submissionId" element={<MySubmission />} />
            </>
          )}
          <Route path="*" element={<Navigate to={HOME[user.role]} replace />} />
        </Routes>
      </main>
    </div>
  );
}
