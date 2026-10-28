import { Navigate, NavLink, Route, Routes } from "react-router-dom";
import { useAuth } from "./auth.jsx";
import Login from "./pages/Login.jsx";
import { AdminAudit, AdminCourses, AdminUsers } from "./pages/Admin.jsx";
import { Assignment, Course, TeacherHome } from "./pages/Teacher.jsx";
import Run from "./pages/Run.jsx";
import Pair from "./pages/Pair.jsx";
import Review from "./pages/Review.jsx";
import { MyFlags, MySubmission } from "./pages/Student.jsx";

const HOME = { admin: "/admin/users", teacher: "/courses", student: "/me" };

const NAV = {
  admin: [["/admin/users", "Users"], ["/admin/courses", "Courses"], ["/admin/audit", "Audit log"]],
  teacher: [["/courses", "My courses"]],
  student: [["/me", "My flags"]],
};

export default function App() {
  const { user, ready, logout } = useAuth();
  if (!ready) return null;
  if (!user) return <Login />;

  return (
    <div className="shell">
      <header className="topbar">
        <span className="brand">CodeTwin</span>
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
              <Route path="/submissions/:submissionId" element={<MySubmission />} />
            </>
          )}
          <Route path="*" element={<Navigate to={HOME[user.role]} replace />} />
        </Routes>
      </main>
    </div>
  );
}
